"""Data models for Databricks charging attempt investigation."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class ChargingAttemptRecord:
    """attempt 表中的单行充电尝试记录，保留设备、connector、起止时间、充电量和原始行。"""

    sso_id: str
    connector_id: int
    charging_attempt_start: dt.datetime
    charging_attempt_end: dt.datetime
    session_consumption_kwh: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class MergedChargingAttempt:
    """合并后的用户级充电尝试，表示一次真实充电行为在一个 connector 上的汇总时间窗。"""

    sso_id: str
    connector_id: int
    attempt_start: dt.datetime
    attempt_end: dt.datetime
    attempt_count: int
    total_consumption_kwh: float
    evse_id: Optional[str] = None
    original_records: list[ChargingAttemptRecord] = field(default_factory=list)

    @property
    def duration_seconds(self) -> int:
        """返回合并后 attempt 的持续时长，单位秒，用于和 OCPP 状态序列对照。"""
        return int((self.attempt_end - self.attempt_start).total_seconds())

    @classmethod
    def from_records(
        cls,
        records: list[ChargingAttemptRecord],
        *,
        sso_id: str,
        connector_id: int,
        evse_id: Optional[str] = None,
    ) -> "MergedChargingAttempt":
        """从同一设备和 connector 的多行 attempt 构造一次用户级尝试。"""
        if not records:
            raise ValueError("records cannot be empty")

        return cls(
            sso_id=sso_id,
            evse_id=evse_id,
            connector_id=connector_id,
            attempt_start=min(record.charging_attempt_start for record in records),
            attempt_end=max(record.charging_attempt_end for record in records),
            attempt_count=len(records),
            total_consumption_kwh=sum(record.session_consumption_kwh for record in records),
            original_records=records,
        )

    def as_dict(self) -> dict[str, Any]:
        """输出适合日志、调研展示和后续 JSON 序列化的 attempt 摘要。"""
        return {
            "sso_id": self.sso_id,
            "evse_id": self.evse_id,
            "connector_id": self.connector_id,
            "attempt_start": self.attempt_start,
            "attempt_end": self.attempt_end,
            "duration_seconds": self.duration_seconds,
            "attempt_count": self.attempt_count,
            "total_consumption_kwh": self.total_consumption_kwh,
        }


@dataclass(frozen=True)
class OCPPEvent:
    """OCPP 操作事件模型，表示设备在某个时间点发出的单条 request/response 消息。"""

    sso_id: str
    operation_timestamp: dt.datetime
    ocpp_message_type: str
    ocpp_request_body: Optional[str] = None
    ocpp_response_body: Optional[str] = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OCPPSequenceResult:
    """一次 attempt 对应的 OCPP 调研结果，包含 attempt 元数据、原始事件和格式化事件。"""

    attempt: MergedChargingAttempt
    raw_events: list[OCPPEvent]
    formatted_events: list[dict[str, Any]]
