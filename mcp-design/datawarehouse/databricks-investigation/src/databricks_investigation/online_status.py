"""MCP-friendly device online status query API."""

from __future__ import annotations

import datetime as dt
from typing import Optional

from .databricks_client import DatabricksClient
from .models import OCPPEvent
from .timestamp_utils import coerce_datetime


class DeviceOnlineStatusQuery:
    """基于 OCPP Heartbeat 和最近事件判断设备在线质量，返回掉线区间和最近通信状态。"""

    def __init__(self, client: DatabricksClient):
        self.client = client

    def query(
        self,
        *,
        sso_id: str,
        time_from: dt.datetime | str,
        time_to: dt.datetime | str,
        expected_heartbeat_interval_minutes: int = 15,
        missing_heartbeat_threshold: int = 2,
        recent_grace_minutes: Optional[int] = None,
    ) -> dict:
        """查询指定时间范围内的 Heartbeat 与最近 OCPP 事件，并识别可能离线的时间段。"""
        start = self._require_datetime(time_from, "time_from")
        end = self._require_datetime(time_to, "time_to")
        if start > end:
            raise ValueError("time_from must be earlier than or equal to time_to")
        if expected_heartbeat_interval_minutes <= 0:
            raise ValueError("expected_heartbeat_interval_minutes must be positive")
        if missing_heartbeat_threshold < 1:
            raise ValueError("missing_heartbeat_threshold must be at least 1")

        latest_event = self._query_latest_event(sso_id, start, end)
        heartbeats = self._query_heartbeats(sso_id, start, end)
        offline_periods = self._detect_offline_periods(
            heartbeats,
            expected_interval=dt.timedelta(minutes=expected_heartbeat_interval_minutes),
            missing_threshold=missing_heartbeat_threshold,
        )
        latest_heartbeat = heartbeats[-1] if heartbeats else None
        grace_minutes = recent_grace_minutes or expected_heartbeat_interval_minutes * (
            missing_heartbeat_threshold + 1
        )
        has_recent_heartbeat = (
            latest_heartbeat is not None
            and end - latest_heartbeat.operation_timestamp
            <= dt.timedelta(minutes=grace_minutes)
        )

        return {
            "query": {
                "sso_id": sso_id,
                "time_from": start.isoformat(),
                "time_to": end.isoformat(),
                "expected_heartbeat_interval_minutes": expected_heartbeat_interval_minutes,
                "missing_heartbeat_threshold": missing_heartbeat_threshold,
                "recent_grace_minutes": grace_minutes,
            },
            "latest_ocpp_event": self._event_to_dict(latest_event),
            "latest_heartbeat": self._event_to_dict(latest_heartbeat),
            "heartbeat_count": len(heartbeats),
            "heartbeat_samples": [self._event_to_dict(event) for event in heartbeats[-20:]],
            "offline_periods": offline_periods,
            "online_summary": {
                "has_recent_heartbeat": has_recent_heartbeat,
                "has_offline_gap": bool(offline_periods),
                "status": self._status_label(has_recent_heartbeat, bool(offline_periods)),
            },
        }

    def _query_latest_event(
        self,
        sso_id: str,
        time_from: dt.datetime,
        time_to: dt.datetime,
    ) -> Optional[OCPPEvent]:
        table = self.client.settings.table("charger_ocpp_operations_v")
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
        ORDER BY operation_timestamp DESC
        LIMIT 1
        """
        rows = self.client.execute(query, [sso_id, time_from, time_to]).as_dicts()
        return self._event_from_row(rows[0]) if rows else None

    def _query_heartbeats(
        self,
        sso_id: str,
        time_from: dt.datetime,
        time_to: dt.datetime,
    ) -> list[OCPPEvent]:
        table = self.client.settings.table("charger_ocpp_operations_v")
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
          AND ocpp_message_type = 'Heartbeat'
        ORDER BY operation_timestamp ASC
        """
        return [
            self._event_from_row(row)
            for row in self.client.execute(query, [sso_id, time_from, time_to]).as_dicts()
        ]

    def _detect_offline_periods(
        self,
        heartbeats: list[OCPPEvent],
        *,
        expected_interval: dt.timedelta,
        missing_threshold: int,
    ) -> list[dict]:
        periods: list[dict] = []
        if len(heartbeats) < 2:
            return periods

        offline_threshold = expected_interval * (missing_threshold + 1)
        expected_seconds = expected_interval.total_seconds()
        for previous, current in zip(heartbeats, heartbeats[1:]):
            gap = current.operation_timestamp - previous.operation_timestamp
            if gap <= offline_threshold:
                continue
            missed = max(0, round(gap.total_seconds() / expected_seconds) - 1)
            periods.append(
                {
                    "from": previous.operation_timestamp.isoformat(),
                    "to": current.operation_timestamp.isoformat(),
                    "gap_minutes": round(gap.total_seconds() / 60, 3),
                    "missed_heartbeat_count_estimate": missed,
                }
            )
        return periods

    def _status_label(self, has_recent_heartbeat: bool, has_offline_gap: bool) -> str:
        if not has_recent_heartbeat:
            return "stale_or_offline"
        if has_offline_gap:
            return "online_with_gaps"
        return "normal"

    def _event_from_row(self, row: dict) -> OCPPEvent:
        timestamp = self._require_datetime(row["operation_timestamp"], "operation_timestamp")
        return OCPPEvent(
            sso_id=row["sso_id"],
            operation_timestamp=timestamp,
            ocpp_message_type=row["ocpp_message_type"],
            ocpp_request_body=row.get("ocpp_request_body"),
            ocpp_response_body=row.get("ocpp_response_body"),
            raw=row,
        )

    def _event_to_dict(self, event: Optional[OCPPEvent]) -> Optional[dict]:
        if event is None:
            return None
        return {
            "sso_id": event.sso_id,
            "operation_timestamp": event.operation_timestamp.isoformat(),
            "ocpp_message_type": event.ocpp_message_type,
        }

    def _require_datetime(self, value: dt.datetime | str, name: str) -> dt.datetime:
        parsed = coerce_datetime(value)
        if parsed is None:
            raise ValueError(f"{name} is required")
        return parsed
