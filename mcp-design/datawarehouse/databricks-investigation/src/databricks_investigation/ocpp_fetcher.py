"""Fetch OCPP event sequences for merged charging attempts."""

from __future__ import annotations

import datetime as dt

from .databricks_client import DatabricksClient
from .models import MergedChargingAttempt, OCPPEvent
from .timestamp_utils import coerce_datetime


class OCPPFetcher:
    """OCPP 序列获取 API：根据设备和时间窗查询 Databricks 中的 OCPP 操作事件。"""

    def __init__(self, client: DatabricksClient):
        self.client = client

    def fetch_events(
        self,
        *,
        sso_id: str,
        start_time: dt.datetime,
        end_time: dt.datetime,
        include_heartbeats: bool = False,
    ) -> list[OCPPEvent]:
        """查询指定设备在时间范围内的 OCPP 原始事件，默认排除 Heartbeat 噪声。"""
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

        result = self.client.execute(query, [sso_id, query_start, query_end])
        return [self._event_from_row(row) for row in result.as_dicts()]

    def expand_boundaries(
        self,
        events: list[OCPPEvent],
        attempt: MergedChargingAttempt,
    ) -> tuple[dt.datetime, dt.datetime]:
        """根据边界附近的 OCPP 事件给 attempt 时间窗做诊断友好的微扩展。"""
        if not events:
            return attempt.attempt_start, attempt.attempt_end

        threshold = dt.timedelta(milliseconds=self.client.settings.ocpp_boundary_expand_ms)
        new_start = attempt.attempt_start
        new_end = attempt.attempt_end

        before_start = sorted(
            [event for event in events if event.operation_timestamp < attempt.attempt_start],
            key=lambda event: event.operation_timestamp,
            reverse=True,
        )
        current = attempt.attempt_start
        for event in before_start:
            if current - event.operation_timestamp <= threshold:
                new_start = event.operation_timestamp
                current = event.operation_timestamp
            else:
                break

        after_end = sorted(
            [event for event in events if event.operation_timestamp > attempt.attempt_end],
            key=lambda event: event.operation_timestamp,
        )
        current = attempt.attempt_end
        for event in after_end:
            if event.operation_timestamp - current <= threshold:
                new_end = event.operation_timestamp
                current = event.operation_timestamp
            else:
                break

        return new_start, new_end

    def fetch_sequence_for_attempt(
        self,
        attempt: MergedChargingAttempt,
        *,
        include_heartbeats: bool = False,
    ) -> list[OCPPEvent]:
        """按合并后的 attempt 获取最终 OCPP 序列，是 attempt 到协议事件链路的主入口。"""
        events = self.fetch_events(
            sso_id=attempt.sso_id,
            start_time=attempt.attempt_start,
            end_time=attempt.attempt_end,
            include_heartbeats=include_heartbeats,
        )
        if not events:
            return []

        start, end = self.expand_boundaries(events, attempt)
        return [
            event
            for event in events
            if start <= event.operation_timestamp <= end
        ]

    def _event_from_row(self, row: dict) -> OCPPEvent:
        timestamp = coerce_datetime(row["operation_timestamp"])
        if timestamp is None:
            raise ValueError(f"OCPP row has invalid timestamp: {row}")

        return OCPPEvent(
            sso_id=row["sso_id"],
            operation_timestamp=timestamp,
            ocpp_message_type=row["ocpp_message_type"],
            ocpp_request_body=row.get("ocpp_request_body"),
            ocpp_response_body=row.get("ocpp_response_body"),
            raw=row,
        )
