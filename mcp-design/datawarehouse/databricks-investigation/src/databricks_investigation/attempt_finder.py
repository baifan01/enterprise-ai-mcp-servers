"""Find and merge charging attempt rows from Databricks."""

from __future__ import annotations

import datetime as dt
from typing import Optional

from .databricks_client import DatabricksClient
from .models import ChargingAttemptRecord, MergedChargingAttempt
from .timestamp_utils import coerce_datetime


class AttemptFinder:
    """充电尝试定位 API：根据设备标识和时间点查询候选 attempt，并汇总成一次用户级尝试。"""

    MERGE_START_THRESHOLD_SECONDS = 60
    CONTIGUOUS_GAP_THRESHOLD_SECONDS = 300

    def __init__(self, client: DatabricksClient):
        self.client = client

    def lookup_sso_by_evse(self, evse_id: str) -> Optional[str]:
        """将用户提供的 EVSE ID 映射为 attempt/OCPP 查询所需的内部 SSO ID。"""
        table = self.client.settings.table("charger_location_charger_v")
        query = f"""
        SELECT sso_id
        FROM {table}
        WHERE evse_id LIKE ?
          AND (sso_valid_to IS NULL OR sso_valid_to > CURRENT_DATE())
        LIMIT 1
        """
        result = self.client.execute(query, [f"%{evse_id}%"])
        if not result.rows:
            return None
        return result.rows[0][0]

    def find_nearby_attempts(
        self,
        input_timestamp: dt.datetime,
        *,
        sso_id: Optional[str] = None,
        evse_id: Optional[str] = None,
    ) -> list[ChargingAttemptRecord]:
        """查询某设备在输入时间点附近的原始 attempt 行，用于查看候选充电尝试和业务状态。"""
        resolved_sso_id = sso_id or (self.lookup_sso_by_evse(evse_id) if evse_id else None)
        if not resolved_sso_id:
            raise ValueError("sso_id is required, or evse_id must resolve to an sso_id")

        window = dt.timedelta(minutes=self.client.settings.attempt_search_window_minutes)
        start_window = input_timestamp - window
        end_window = input_timestamp + window
        table = self.client.settings.table("kpi_charging_attempts_enriched_v")

        query = f"""
        SELECT
            source_device_id AS sso_id,
            ocpi_connector_id AS connector_id,
            charging_attempt_start,
            charging_attempt_end,
            session_consumption_kwh,
            transaction_id,
            transaction_stop_reason,
            authorization_status,
            session_status,
            remote_start_status
        FROM {table}
        WHERE source_device_id = ?
          AND (
            charging_attempt_start BETWEEN ? AND ?
            OR ? BETWEEN charging_attempt_start AND charging_attempt_end
            OR charging_attempt_end BETWEEN ? AND ?
          )
        ORDER BY ocpi_connector_id, charging_attempt_start
        """

        result = self.client.execute(
            query,
            [resolved_sso_id, start_window, end_window, input_timestamp, start_window, end_window],
        )
        return [self._record_from_row(row) for row in result.as_dicts()]

    def find_and_merge(
        self,
        input_timestamp: dt.datetime,
        *,
        sso_id: Optional[str] = None,
        evse_id: Optional[str] = None,
    ) -> list[MergedChargingAttempt]:
        """查询并合并用户级充电尝试，作为后续抓取 OCPP 序列的标准入口。"""
        records = self.find_nearby_attempts(input_timestamp, sso_id=sso_id, evse_id=evse_id)
        if not records:
            return []

        anchor = self.select_anchor_record(input_timestamp, records)
        adjacent = self.find_adjacent_records(anchor, records)
        return [
            MergedChargingAttempt.from_records(
                adjacent,
                sso_id=anchor.sso_id,
                evse_id=evse_id,
                connector_id=anchor.connector_id,
            )
        ]

    def select_anchor_record(
        self,
        input_timestamp: dt.datetime,
        records: list[ChargingAttemptRecord],
    ) -> ChargingAttemptRecord:
        """从候选 attempt 中选出最能代表用户输入时间点的锚点记录。"""
        if not records:
            raise ValueError("records cannot be empty")

        containing = [
            record
            for record in records
            if record.charging_attempt_start <= input_timestamp <= record.charging_attempt_end
        ]
        if containing:
            return min(containing, key=lambda record: record.charging_attempt_start)

        def distance(record: ChargingAttemptRecord) -> float:
            if input_timestamp < record.charging_attempt_start:
                return (record.charging_attempt_start - input_timestamp).total_seconds()
            return (input_timestamp - record.charging_attempt_end).total_seconds()

        return min(records, key=distance)

    def find_adjacent_records(
        self,
        anchor_record: ChargingAttemptRecord,
        all_records: list[ChargingAttemptRecord],
    ) -> list[ChargingAttemptRecord]:
        """围绕锚点找出同一设备和 connector 上应视为同一次用户尝试的相邻记录。"""
        connector_records = sorted(
            [
                record
                for record in all_records
                if record.connector_id == anchor_record.connector_id
                and record.sso_id == anchor_record.sso_id
            ],
            key=lambda record: record.charging_attempt_start,
        )

        selected = [anchor_record]
        selected_ids = {id(anchor_record)}
        changed = True
        while changed:
            changed = False
            for record in connector_records:
                if id(record) in selected_ids:
                    continue
                if any(self._is_adjacent(record, existing) for existing in selected):
                    selected.append(record)
                    selected_ids.add(id(record))
                    changed = True

        return sorted(selected, key=lambda record: record.charging_attempt_start)

    def _is_adjacent(
        self,
        first: ChargingAttemptRecord,
        second: ChargingAttemptRecord,
    ) -> bool:
        start_diff = abs(
            (first.charging_attempt_start - second.charging_attempt_start).total_seconds()
        )
        if start_diff <= self.MERGE_START_THRESHOLD_SECONDS:
            return True

        if first.charging_attempt_end <= second.charging_attempt_start:
            gap = (second.charging_attempt_start - first.charging_attempt_end).total_seconds()
            return gap <= self.CONTIGUOUS_GAP_THRESHOLD_SECONDS

        if second.charging_attempt_end <= first.charging_attempt_start:
            gap = (first.charging_attempt_start - second.charging_attempt_end).total_seconds()
            return gap <= self.CONTIGUOUS_GAP_THRESHOLD_SECONDS

        return False

    def _record_from_row(self, row: dict) -> ChargingAttemptRecord:
        start = coerce_datetime(row["charging_attempt_start"])
        end = coerce_datetime(row["charging_attempt_end"])
        if start is None or end is None:
            raise ValueError(f"Attempt row has invalid timestamps: {row}")

        return ChargingAttemptRecord(
            sso_id=row["sso_id"],
            connector_id=int(row["connector_id"] or 0),
            charging_attempt_start=start,
            charging_attempt_end=end,
            session_consumption_kwh=float(row.get("session_consumption_kwh") or 0),
            raw=row,
        )
