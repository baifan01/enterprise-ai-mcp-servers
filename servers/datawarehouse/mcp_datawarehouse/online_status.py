"""Device online status query using the legacy Heartbeat gap rule.

This module owns the Databricks OCPP reads needed for a single-device time
window: the event before the window, all events inside the window, and
optionally the first event after the window. The actual gap detection stays in
heartbeat_gap.py so SQL access and legacy-compatible state logic remain
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

ONLINE_STATUS_PREVIOUS_EVENT_QUERY = "charger_ocpp_operations_v.online_status.previous_event"
ONLINE_STATUS_WINDOW_EVENTS_QUERY = "charger_ocpp_operations_v.online_status.window_events"
ONLINE_STATUS_NEXT_EVENT_QUERY = "charger_ocpp_operations_v.online_status.next_event"
EDGE_EVENT_LOOKAROUND_SECONDS = 86_400

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
        if heartbeat_interval_seconds <= 0:
            raise ValueError("heartbeat_interval_seconds must be positive")
        if missed_heartbeat_tolerance < 1:
            raise ValueError("missed_heartbeat_tolerance must be at least 1")
        if recent_end_grace_seconds < 0:
            raise ValueError("recent_end_grace_seconds must be non-negative")

        threshold_seconds = heartbeat_interval_seconds * (missed_heartbeat_tolerance + 1)
        current_time = self._normalize_now(now)
        edge_lookaround = dt.timedelta(seconds=EDGE_EVENT_LOOKAROUND_SECONDS)

        logger.info(
            "Starting online status analysis: sso_id=%s time_from=%s time_to=%s "
            "offline_threshold_seconds=%s edge_event_lookaround_seconds=%s",
            normalized_sso_id,
            start,
            end,
            threshold_seconds,
            EDGE_EVENT_LOOKAROUND_SECONDS,
        )
        previous_event = await self._query_previous_event(
            normalized_sso_id,
            lookback_start=start - edge_lookaround,
            analysis_start=start,
        )
        window_events = await self._query_window_events(normalized_sso_id, start, end)
        next_event = None
        should_query_next = end < current_time and (
            current_time - end
        ).total_seconds() > recent_end_grace_seconds
        if should_query_next:
            next_event = await self._query_next_event(
                normalized_sso_id,
                analysis_end=end,
                lookahead_end=end + edge_lookaround,
            )

        analysis_events = [event for event in [previous_event, *window_events, next_event] if event]
        offline_periods = analyze_heartbeat_gaps(
            analysis_events,
            analysis_start=start,
            analysis_end=end,
            offline_threshold_seconds=threshold_seconds,
        )
        latest_event = self._latest_event_before_or_at_end(
            previous_event=previous_event,
            window_events=window_events,
            end=end,
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
                "edge_event_lookaround_seconds": EDGE_EVENT_LOOKAROUND_SECONDS,
                "recent_end_grace_seconds": recent_end_grace_seconds,
                "queried_next_event_after_window": should_query_next,
            },
            "has_offline": bool(offline_periods),
            "offline_periods": [offline_period_to_dict(period) for period in offline_periods],
            "latest_event_before_or_at_end": self._event_to_dict(latest_event),
            "previous_event_before_window": self._event_to_dict(previous_event),
            "next_event_after_window": self._event_to_dict(next_event),
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
            ocpp_message_type
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

    async def _query_previous_event(
        self,
        sso_id: str,
        *,
        lookback_start: dt.datetime,
        analysis_start: dt.datetime,
    ) -> OCPPEvent | None:
        table = self.client.settings.table("charger_ocpp_operations_v")
        logger.info(
            "Querying online status previous event: sso_id=%s lookback_start=%s before=%s",
            sso_id,
            lookback_start,
            analysis_start,
        )
        query = f"""
        SELECT
            sso_id,
            operation_timestamp,
            ocpp_message_type
        FROM {table}
        WHERE sso_id = ?
          AND operation_timestamp >= ?
          AND operation_timestamp < ?
        ORDER BY operation_timestamp DESC
        LIMIT 1
        """
        result = await self.client.execute(
            query,
            [sso_id, lookback_start, analysis_start],
            source_query=ONLINE_STATUS_PREVIOUS_EVENT_QUERY,
        )
        rows = result.as_dicts()
        event = self._event_from_row(rows[0]) if rows else None
        logger.info(
            "Online status previous event loaded: sso_id=%s found=%s",
            sso_id,
            event is not None,
        )
        return event

    async def _query_next_event(
        self,
        sso_id: str,
        *,
        analysis_end: dt.datetime,
        lookahead_end: dt.datetime,
    ) -> OCPPEvent | None:
        table = self.client.settings.table("charger_ocpp_operations_v")
        logger.info(
            "Querying online status next event: sso_id=%s after=%s lookahead_end=%s",
            sso_id,
            analysis_end,
            lookahead_end,
        )
        query = f"""
        SELECT
            sso_id,
            operation_timestamp,
            ocpp_message_type
        FROM {table}
        WHERE sso_id = ?
          AND operation_timestamp > ?
          AND operation_timestamp <= ?
        ORDER BY operation_timestamp ASC
        LIMIT 1
        """
        result = await self.client.execute(
            query,
            [sso_id, analysis_end, lookahead_end],
            source_query=ONLINE_STATUS_NEXT_EVENT_QUERY,
        )
        rows = result.as_dicts()
        event = self._event_from_row(rows[0]) if rows else None
        logger.info(
            "Online status next event loaded: sso_id=%s found=%s",
            sso_id,
            event is not None,
        )
        return event

    def _event_from_row(self, row: dict[str, Any]) -> OCPPEvent:
        timestamp = self._require_datetime(row["operation_timestamp"], "operation_timestamp")
        return OCPPEvent(
            sso_id=str(row["sso_id"]),
            operation_timestamp=timestamp,
            ocpp_message_type=str(row["ocpp_message_type"]),
            raw=row,
        )

    def _latest_event_before_or_at_end(
        self,
        *,
        previous_event: OCPPEvent | None,
        window_events: list[OCPPEvent],
        end: dt.datetime,
    ) -> OCPPEvent | None:
        candidates = [event for event in [previous_event, *window_events] if event]
        before_or_at_end = [event for event in candidates if event.operation_timestamp <= end]
        if not before_or_at_end:
            return None
        return max(before_or_at_end, key=lambda event: event.operation_timestamp)

    def _event_to_dict(self, event: OCPPEvent | None) -> dict[str, Any] | None:
        if event is None:
            return None
        return {
            "sso_id": event.sso_id,
            "event_time": event.operation_timestamp.isoformat(),
            "event_type": event.ocpp_message_type,
        }

    def _normalize_now(self, value: dt.datetime | None) -> dt.datetime:
        if value is None:
            return dt.datetime.utcnow()
        return value.replace(tzinfo=None)

    def _require_datetime(self, value: dt.datetime | str, name: str) -> dt.datetime:
        parsed = coerce_datetime(value)
        if parsed is None:
            raise ValueError(f"{name} is required")
        return parsed
