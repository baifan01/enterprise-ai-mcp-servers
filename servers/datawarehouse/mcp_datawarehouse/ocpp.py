"""OCPP event sequence query and compact formatting logic.

This module owns OCPP warehouse table semantics and compact AI-facing event
summaries. It intentionally avoids MCP transport concerns and keeps large raw
payloads hidden unless the caller explicitly asks for bounded snippets.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from typing import Any, Protocol

from mcp_datawarehouse.models import OCPPEvent, QueryResult
from mcp_datawarehouse.settings import DatawarehouseSettings
from mcp_datawarehouse.timestamp_utils import coerce_datetime

OCPP_SOURCE_QUERY = "charger_ocpp_operations_v"


class QueryClient(Protocol):
    settings: DatawarehouseSettings

    async def execute(
        self,
        query: str,
        parameters: list[Any] | None = None,
        *,
        source_query: str,
    ) -> QueryResult:
        ...


class OCPPFetcher:
    """Fetch OCPP operation events from Databricks."""

    def __init__(self, client: QueryClient) -> None:
        self.client = client

    async def fetch_events(
        self,
        *,
        sso_id: str,
        start_time: dt.datetime,
        end_time: dt.datetime,
        include_heartbeats: bool = False,
    ) -> list[OCPPEvent]:
        buffer = dt.timedelta(seconds=self.client.settings.ocpp_time_buffer_seconds)
        query_start = start_time - buffer
        query_end = end_time + buffer
        table = self.client.settings.table("charger_ocpp_operations_v")

        heartbeat_clause = "" if include_heartbeats else "AND ocpp_message_type != 'Heartbeat'"
        query = f"""
        SELECT
            REGEXP_EXTRACT(sso_id, '^([^_]+)', 1) AS sso_id,
            operation_timestamp,
            ocpp_message_type,
            ocpp_request_body,
            ocpp_response_body
        FROM {table}
        WHERE REGEXP_EXTRACT(sso_id, '^([^_]+)', 1) = ?
          AND operation_timestamp >= ?
          AND operation_timestamp <= ?
          {heartbeat_clause}
        ORDER BY operation_timestamp ASC
        """

        result = await self.client.execute(
            query,
            [sso_id, query_start, query_end],
            source_query=OCPP_SOURCE_QUERY,
        )
        return [self._event_from_row(row) for row in result.as_dicts()]

    def _event_from_row(self, row: dict[str, Any]) -> OCPPEvent:
        timestamp = coerce_datetime(row["operation_timestamp"])
        if timestamp is None:
            raise ValueError(f"OCPP row has invalid timestamp: {row}")

        return OCPPEvent(
            sso_id=str(row["sso_id"]),
            operation_timestamp=timestamp,
            ocpp_message_type=str(row["ocpp_message_type"]),
            ocpp_request_body=row.get("ocpp_request_body"),
            ocpp_response_body=row.get("ocpp_response_body"),
            raw=row,
        )


class OCPPFormatter:
    """Format raw OCPP events into compact event timelines."""

    CONNECTOR_ID_KEYS = ("connectorId", "connector_id", "connectorID")

    def format_event(self, event: OCPPEvent, anchor_time: dt.datetime) -> dict[str, Any]:
        offset = round((event.operation_timestamp - anchor_time).total_seconds(), 3)
        result: dict[str, Any] = {
            "time_offset_seconds": offset,
            "operation_timestamp": event.operation_timestamp.isoformat(),
            "ocpp_type": event.ocpp_message_type,
        }

        connector_id = self.extract_connector_id(event.ocpp_request_body)
        if connector_id is None:
            connector_id = self.extract_connector_id(event.ocpp_response_body)
        if connector_id is not None:
            result["connector_id"] = connector_id

        if event.ocpp_message_type == "StatusNotification":
            result["status_info"] = self.extract_status_notification(event.ocpp_request_body)
        elif event.ocpp_message_type != "MeterValues":
            if event.ocpp_request_body:
                result["request"] = event.ocpp_request_body
            if event.ocpp_response_body:
                result["response"] = event.ocpp_response_body

        return result

    def extract_connector_id(self, body: str | None) -> int | None:
        if not body:
            return None

        try:
            parsed = json.loads(body)
            payloads = parsed if isinstance(parsed, list) else [parsed]
            for payload in payloads:
                if not isinstance(payload, dict):
                    continue
                for key in self.CONNECTOR_ID_KEYS:
                    if key in payload:
                        return int(payload[key])
        except (TypeError, ValueError, json.JSONDecodeError):
            pass

        for pattern in (
            r'"connectorId"\s*:\s*(\d+)',
            r'"connector_id"\s*:\s*(\d+)',
            r'"connectorID"\s*:\s*(\d+)',
        ):
            match = re.search(pattern, body, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return None

    def extract_status_notification(self, request_body: str | None) -> dict[str, str]:
        if not request_body:
            return {"errorCode": "Unknown", "status": "Unknown"}
        return {
            "errorCode": self._extract_string_field(request_body, "errorCode") or "Unknown",
            "status": self._extract_string_field(request_body, "status") or "Unknown",
        }

    def _extract_string_field(self, body: str, field_name: str) -> str | None:
        pattern = rf'"{re.escape(field_name)}"\s*:\s*"([^"]*)"'
        match = re.search(pattern, body)
        return match.group(1) if match else None


class OCPPSequenceQuery:
    """Query OCPP events and produce compact AI-facing summaries."""

    def __init__(self, client: QueryClient) -> None:
        self.client = client
        self._fetcher = OCPPFetcher(client)
        self._formatter = OCPPFormatter()

    async def query(
        self,
        *,
        sso_id: str,
        time_from: dt.datetime | str,
        time_to: dt.datetime | str,
        include_heartbeats: bool = False,
        include_raw_payload: bool = False,
        max_payload_chars: int = 1200,
    ) -> dict[str, Any]:
        normalized_sso_id = sso_id.strip()
        if not normalized_sso_id:
            raise ValueError("sso_id must not be empty")
        start = self._require_datetime(time_from, "time_from")
        end = self._require_datetime(time_to, "time_to")
        if start > end:
            raise ValueError("time_from must be earlier than or equal to time_to")
        if max_payload_chars < 100:
            raise ValueError("max_payload_chars must be at least 100")

        events = await self._fetcher.fetch_events(
            sso_id=normalized_sso_id,
            start_time=start,
            end_time=end,
            include_heartbeats=include_heartbeats,
        )
        anchor_time = events[0].operation_timestamp if events else start
        compact_events = [
            self._compact_event(event, anchor_time, include_raw_payload, max_payload_chars)
            for event in events
        ]

        return {
            "query": {
                "sso_id": normalized_sso_id,
                "time_from": start.isoformat(),
                "time_to": end.isoformat(),
                "include_heartbeats": include_heartbeats,
                "include_raw_payload": include_raw_payload,
                "max_payload_chars": max_payload_chars,
            },
            "event_count": len(events),
            "event_type_counts": self._event_type_counts(events),
            "events": compact_events,
        }

    def _compact_event(
        self,
        event: OCPPEvent,
        anchor_time: dt.datetime,
        include_raw_payload: bool,
        max_payload_chars: int,
    ) -> dict[str, Any]:
        formatted = self._formatter.format_event(event, anchor_time)
        request_summary = self._payload_summary(event.ocpp_request_body)
        response_summary = self._payload_summary(event.ocpp_response_body)

        compact: dict[str, Any] = {
            "timestamp": event.operation_timestamp.isoformat(),
            "offset_seconds": formatted["time_offset_seconds"],
            "ocpp_type": event.ocpp_message_type,
            "payload_lengths": {
                "request_chars": len(event.ocpp_request_body or ""),
                "response_chars": len(event.ocpp_response_body or ""),
            },
        }
        if "connector_id" in formatted:
            compact["connector_id"] = formatted["connector_id"]
        if "status_info" in formatted:
            compact["status"] = formatted["status_info"].get("status")
            compact["error_code"] = formatted["status_info"].get("errorCode")
        if request_summary is not None:
            compact["request_summary"] = request_summary
        if response_summary is not None:
            compact["response_summary"] = response_summary

        if include_raw_payload:
            if event.ocpp_request_body:
                compact["request"] = self._truncate(event.ocpp_request_body, max_payload_chars)
            if event.ocpp_response_body:
                compact["response"] = self._truncate(event.ocpp_response_body, max_payload_chars)

        return compact

    def _payload_summary(self, body: str | None) -> dict[str, Any] | None:
        if not body:
            return None

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return {"raw_length": len(body), "json": False}

        summary: dict[str, Any] = {"json": True}
        candidates = payload if isinstance(payload, list) else [payload]
        for item in candidates:
            if not isinstance(item, dict):
                continue
            for key in (
                "status",
                "errorCode",
                "connectorId",
                "transactionId",
                "idTag",
                "reason",
                "meterStart",
                "meterStop",
                "timestamp",
            ):
                if key in item:
                    summary[key] = item[key]
            id_tag_info = item.get("idTagInfo")
            if isinstance(id_tag_info, dict):
                summary["idTagInfo"] = {
                    key: id_tag_info.get(key)
                    for key in ("status", "expiryDate", "parentIdTag")
                    if key in id_tag_info
                }

        if len(summary) == 1:
            summary["raw_length"] = len(body)
        return summary

    def _truncate(self, value: str, max_chars: int) -> dict[str, Any]:
        if len(value) <= max_chars:
            return {"truncated": False, "text": value}
        return {
            "truncated": True,
            "original_chars": len(value),
            "text": value[:max_chars],
        }

    def _event_type_counts(self, events: list[OCPPEvent]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for event in events:
            counts[event.ocpp_message_type] = counts.get(event.ocpp_message_type, 0) + 1
        return dict(sorted(counts.items()))

    def _require_datetime(self, value: dt.datetime | str, name: str) -> dt.datetime:
        parsed = coerce_datetime(value)
        if parsed is None:
            raise ValueError(f"{name} is required")
        return parsed
