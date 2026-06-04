"""MCP-friendly OCPP sequence query API."""

from __future__ import annotations

import datetime as dt
import json
from typing import Any, Optional

from .databricks_client import DatabricksClient
from .models import OCPPEvent
from .ocpp_fetcher import OCPPFetcher
from .ocpp_formatter import OCPPFormatter
from .timestamp_utils import coerce_datetime


class OCPPSequenceQuery:
    """按设备和时间范围查询 OCPP 时序，并返回适合 AI 判断的紧凑事件列表。"""

    def __init__(self, client: DatabricksClient):
        self.client = client
        self._fetcher = OCPPFetcher(client)
        self._formatter = OCPPFormatter()

    def query(
        self,
        *,
        sso_id: str,
        time_from: dt.datetime | str,
        time_to: dt.datetime | str,
        include_heartbeats: bool = False,
        include_raw_payload: bool = False,
        max_payload_chars: int = 1200,
    ) -> dict:
        """查询 OCPP 原始事件并生成紧凑摘要，默认隐藏大体积 request/response 原文。"""
        start = self._require_datetime(time_from, "time_from")
        end = self._require_datetime(time_to, "time_to")
        if start > end:
            raise ValueError("time_from must be earlier than or equal to time_to")
        if max_payload_chars < 100:
            raise ValueError("max_payload_chars must be at least 100")

        events = self._fetcher.fetch_events(
            sso_id=sso_id,
            start_time=start,
            end_time=end,
            include_heartbeats=include_heartbeats,
        )
        compact_events = [
            self._compact_event(
                event,
                events[0].operation_timestamp,
                include_raw_payload,
                max_payload_chars,
            )
            for event in events
        ]

        return {
            "query": {
                "sso_id": sso_id,
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

    def _payload_summary(self, body: Optional[str]) -> Optional[dict[str, Any]]:
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
