"""MCP-friendly charging attempt query API."""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from typing import Optional

from .attempt_finder import AttemptFinder
from .databricks_client import DatabricksClient
from .models import ChargingAttemptRecord, MergedChargingAttempt
from .timestamp_utils import coerce_datetime


class ChargingAttemptsQuery:
    """按设备和时间范围查询充电尝试，并返回适合 AI/MCP 消费的原始与合并结果。"""

    def __init__(self, client: DatabricksClient):
        self.client = client
        self._attempt_finder = AttemptFinder(client)

    def query(
        self,
        *,
        time_from: dt.datetime | str,
        time_to: dt.datetime | str,
        sso_id: Optional[str] = None,
        evse_id: Optional[str] = None,
    ) -> dict:
        """查询指定设备在时间范围内的 attempt，必要时将抖动行合并成用户级尝试。"""
        start = self._require_datetime(time_from, "time_from")
        end = self._require_datetime(time_to, "time_to")
        if start > end:
            raise ValueError("time_from must be earlier than or equal to time_to")

        resolved_sso_id = sso_id or (
            self._attempt_finder.lookup_sso_by_evse(evse_id) if evse_id else None
        )
        if not resolved_sso_id:
            raise ValueError("sso_id is required, or evse_id must resolve to an sso_id")

        raw_records = self._query_raw_records(resolved_sso_id, start, end)
        merged_attempts = self.merge_records(raw_records, evse_id=evse_id)
        had_adjacent_merge = any(attempt.attempt_count > 1 for attempt in merged_attempts)

        return {
            "query": {
                "sso_id": resolved_sso_id,
                "evse_id": evse_id,
                "time_from": start.isoformat(),
                "time_to": end.isoformat(),
            },
            "had_adjacent_merge": had_adjacent_merge,
            "raw_attempt_count": len(raw_records),
            "merged_attempt_count": len(merged_attempts),
            "raw_attempts": [self._record_to_dict(record) for record in raw_records],
            "merged_attempts": [self._merged_to_dict(attempt) for attempt in merged_attempts],
        }

    def merge_records(
        self,
        records: list[ChargingAttemptRecord],
        *,
        evse_id: Optional[str] = None,
    ) -> list[MergedChargingAttempt]:
        """将同一 SSO 和 connector 下相邻的 attempt 行合并为用户级充电尝试。"""
        by_device_connector: dict[tuple[str, int], list[ChargingAttemptRecord]] = defaultdict(list)
        for record in records:
            by_device_connector[(record.sso_id, record.connector_id)].append(record)

        merged: list[MergedChargingAttempt] = []
        for (record_sso_id, connector_id), group in by_device_connector.items():
            remaining = sorted(group, key=lambda item: item.charging_attempt_start)
            while remaining:
                anchor = remaining.pop(0)
                adjacent = self._attempt_finder.find_adjacent_records(anchor, [anchor, *remaining])
                adjacent_ids = {id(item) for item in adjacent}
                remaining = [item for item in remaining if id(item) not in adjacent_ids]
                merged.append(
                    MergedChargingAttempt.from_records(
                        adjacent,
                        sso_id=record_sso_id,
                        connector_id=connector_id,
                        evse_id=evse_id,
                    )
                )

        return sorted(merged, key=lambda item: (item.attempt_start, item.connector_id))

    def _query_raw_records(
        self,
        sso_id: str,
        time_from: dt.datetime,
        time_to: dt.datetime,
    ) -> list[ChargingAttemptRecord]:
        table = self.client.settings.table("kpi_charging_attempts_enriched_v")
        query = f"""
        SELECT
            source_device_id AS sso_id,
            ocpi_connector_id AS connector_id,
            charging_attempt_start,
            charging_attempt_end,
            session_consumption_kwh,
            transaction_id,
            transaction_id_tag,
            transaction_stop_reason,
            authorization_status,
            session_status,
            session_charging_duration_seconds,
            seconds_in_preparing,
            seconds_in_charging,
            remote_start_status,
            invalid_session_reasons_from_source,
            has_connector_lock_failure,
            attempt_with_alfen_error_304_timeout
        FROM {table}
        WHERE source_device_id = ?
          AND (
            charging_attempt_start BETWEEN ? AND ?
            OR charging_attempt_end BETWEEN ? AND ?
            OR (charging_attempt_start <= ? AND charging_attempt_end >= ?)
          )
        ORDER BY ocpi_connector_id, charging_attempt_start
        """
        result = self.client.execute(
            query,
            [sso_id, time_from, time_to, time_from, time_to, time_from, time_to],
        )
        return [self._record_from_row(row) for row in result.as_dicts()]

    def _record_from_row(self, row: dict) -> ChargingAttemptRecord:
        start = self._require_datetime(row["charging_attempt_start"], "charging_attempt_start")
        end = self._require_datetime(row["charging_attempt_end"], "charging_attempt_end")
        return ChargingAttemptRecord(
            sso_id=row["sso_id"],
            connector_id=int(row["connector_id"] or 0),
            charging_attempt_start=start,
            charging_attempt_end=end,
            session_consumption_kwh=float(row.get("session_consumption_kwh") or 0),
            raw=row,
        )

    def _record_to_dict(self, record: ChargingAttemptRecord) -> dict:
        raw = record.raw
        return {
            "sso_id": record.sso_id,
            "connector_id": record.connector_id,
            "charging_attempt_start": record.charging_attempt_start.isoformat(),
            "charging_attempt_end": record.charging_attempt_end.isoformat(),
            "duration_seconds": int(
                (record.charging_attempt_end - record.charging_attempt_start).total_seconds()
            ),
            "session_consumption_kwh": record.session_consumption_kwh,
            "session_status": raw.get("session_status"),
            "transaction_id": raw.get("transaction_id"),
            "transaction_id_tag": raw.get("transaction_id_tag"),
            "transaction_stop_reason": raw.get("transaction_stop_reason"),
            "authorization_status": raw.get("authorization_status"),
            "remote_start_status": raw.get("remote_start_status"),
            "session_charging_duration_seconds": raw.get("session_charging_duration_seconds"),
            "seconds_in_preparing": raw.get("seconds_in_preparing"),
            "seconds_in_charging": raw.get("seconds_in_charging"),
            "invalid_session_reasons_from_source": raw.get("invalid_session_reasons_from_source"),
            "has_connector_lock_failure": raw.get("has_connector_lock_failure"),
            "attempt_with_alfen_error_304_timeout": raw.get(
                "attempt_with_alfen_error_304_timeout"
            ),
        }

    def _merged_to_dict(self, attempt: MergedChargingAttempt) -> dict:
        return {
            "sso_id": attempt.sso_id,
            "evse_id": attempt.evse_id,
            "connector_id": attempt.connector_id,
            "attempt_start": attempt.attempt_start.isoformat(),
            "attempt_end": attempt.attempt_end.isoformat(),
            "duration_seconds": attempt.duration_seconds,
            "attempt_count": attempt.attempt_count,
            "total_consumption_kwh": attempt.total_consumption_kwh,
        }

    def _require_datetime(self, value: dt.datetime | str, name: str) -> dt.datetime:
        parsed = coerce_datetime(value)
        if parsed is None:
            raise ValueError(f"{name} is required")
        return parsed
