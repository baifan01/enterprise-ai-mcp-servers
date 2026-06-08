"""Device online status query using the legacy Heartbeat gap rule.

This module owns the Databricks OCPP read needed for a single-device time
window. To keep the live tool responsive, it only reads events inside the
requested range and reports the observed first/last event as coverage metadata;
it does not query events before or after the range. The actual gap detection
stays in heartbeat_gap.py so SQL access and legacy-compatible state logic remain
separate. It intentionally does not read charging attempts or attempt to model a
full device state timeline.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any, Protocol

from mcp_datawarehouse.heartbeat_gap import analyze_heartbeat_gaps, offline_period_to_dict
from mcp_datawarehouse.models import OCPPEvent, QueryResult
from mcp_datawarehouse.settings import DatawarehouseSettings
from mcp_datawarehouse.timestamp_utils import coerce_datetime

ONLINE_STATUS_WINDOW_EVENTS_QUERY = "charger_ocpp_operations_v.online_status.window_events"
ONLINE_STATUS_MAX_WINDOW = dt.timedelta(days=31)

logger = logging.getLogger(__name__)


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


class DeviceOnlineStatusQuery:
    """Query suspicious offline periods for one device and window."""

    def __init__(self, client: QueryClient) -> None:
        self.client = client

    async def query(
        self,
        *,
        sso_id: str,
        time_from: dt.datetime | str,
        time_to: dt.datetime | str,
        heartbeat_interval_seconds: int = 900,
        missed_heartbeat_tolerance: int = 1,
        recent_end_grace_seconds: int = 1800,
        now: dt.datetime | None = None,
    ) -> dict[str, Any]:
        normalized_sso_id = sso_id.strip()
        if not normalized_sso_id:
            raise ValueError("sso_id must not be empty")
        start = self._require_datetime(time_from, "time_from")
        end = self._require_datetime(time_to, "time_to")
        if start > end:
            raise ValueError("time_from must be earlier than or equal to time_to")
        if end - start > ONLINE_STATUS_MAX_WINDOW:
            raise ValueError("online status query is limited to 31 days")
        if heartbeat_interval_seconds <= 0:
            raise ValueError("heartbeat_interval_seconds must be positive")
        if missed_heartbeat_tolerance < 1:
            raise ValueError("missed_heartbeat_tolerance must be at least 1")
        if recent_end_grace_seconds < 0:
            raise ValueError("recent_end_grace_seconds must be non-negative")

        threshold_seconds = heartbeat_interval_seconds * (missed_heartbeat_tolerance + 1)
        logger.info(
            "Starting online status analysis: sso_id=%s time_from=%s time_to=%s "
            "offline_threshold_seconds=%s edge_lookup_enabled=false",
            normalized_sso_id,
            start,
            end,
            threshold_seconds,
        )
        window_events = await self._query_window_events(normalized_sso_id, start, end)
        first_event = window_events[0] if window_events else None
        last_event = window_events[-1] if window_events else None
        observed_start = first_event.operation_timestamp if first_event else start
        observed_end = last_event.operation_timestamp if last_event else end

        offline_periods = analyze_heartbeat_gaps(
            window_events,
            analysis_start=observed_start,
            analysis_end=observed_end,
            offline_threshold_seconds=threshold_seconds,
        )

        total_offline_seconds = sum(period.duration_seconds for period in offline_periods)
        heartbeat_count = sum(1 for event in window_events if event.ocpp_message_type == "Heartbeat")
        logger.info(
            "Completed online status analysis: sso_id=%s event_count_in_window=%s "
            "heartbeat_count_in_window=%s offline_period_count=%s",
            normalized_sso_id,
            len(window_events),
            heartbeat_count,
            len(offline_periods),
        )

        return {
            "query": {
                "sso_id": normalized_sso_id,
                "time_from": start.isoformat(),
                "time_to": end.isoformat(),
                "heartbeat_interval_seconds": heartbeat_interval_seconds,
                "missed_heartbeat_tolerance": missed_heartbeat_tolerance,
                "offline_threshold_seconds": threshold_seconds,
                "recent_end_grace_seconds": recent_end_grace_seconds,
            },
            "coverage": {
                "requested_time_from": start.isoformat(),
                "requested_time_to": end.isoformat(),
                "observed_time_from": observed_start.isoformat() if first_event else None,
                "observed_time_to": observed_end.isoformat() if last_event else None,
                "first_event_in_window": self._event_to_dict(first_event),
                "last_event_in_window": self._event_to_dict(last_event),
                "note": (
                    "Only events inside the requested range were queried. "
                    "Offline state before the first observed event or after the last observed "
                    "event is not inferred."
                ),
            },
            "has_offline": bool(offline_periods),
            "offline_periods": [offline_period_to_dict(period) for period in offline_periods],
            "event_count_in_window": len(window_events),
            "heartbeat_count_in_window": heartbeat_count,
            "summary": {
                "offline_period_count": len(offline_periods),
                "total_offline_seconds": total_offline_seconds,
                "total_offline_minutes": round(total_offline_seconds / 60, 3),
            },
        }

    async def _query_window_events(
        self,
        sso_id: str,
        time_from: dt.datetime,
        time_to: dt.datetime,
    ) -> list[OCPPEvent]:
        table = self.client.settings.table("charger_ocpp_operations_v")
        logger.info(
            "Querying online status window events: sso_id=%s time_from=%s time_to=%s",
            sso_id,
            time_from,
            time_to,
        )
        query = f"""
        SELECT
            sso_id,
            operation_timestamp,
            ocpp_message_type,
            ocpp_request_body
        FROM {table}
        WHERE sso_id = ?
          AND operation_timestamp >= ?
          AND operation_timestamp <= ?
        ORDER BY operation_timestamp ASC
        """
        result = await self.client.execute(
            query,
            [sso_id, time_from, time_to],
            source_query=ONLINE_STATUS_WINDOW_EVENTS_QUERY,
        )
        events = [self._event_from_row(row) for row in result.as_dicts()]
        logger.info(
            "Online status window events loaded: sso_id=%s event_count=%s",
            sso_id,
            len(events),
        )
        return events

    def _event_from_row(self, row: dict[str, Any]) -> OCPPEvent:
        timestamp = self._require_datetime(row["operation_timestamp"], "operation_timestamp")
        return OCPPEvent(
            sso_id=str(row["sso_id"]),
            operation_timestamp=timestamp,
            ocpp_message_type=str(row["ocpp_message_type"]),
            ocpp_request_body=row.get("ocpp_request_body"),
            raw=row,
        )

    def _event_to_dict(self, event: OCPPEvent | None) -> dict[str, Any] | None:
        if event is None:
            return None
        return {
            "sso_id": event.sso_id,
            "event_time": event.operation_timestamp.isoformat(),
            "event_type": event.ocpp_message_type,
        }

    def _require_datetime(self, value: dt.datetime | str, name: str) -> dt.datetime:
        parsed = coerce_datetime(value)
        if parsed is None:
            raise ValueError(f"{name} is required")
        return parsed
