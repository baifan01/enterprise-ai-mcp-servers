"""Domain models for Databricks charging attempt and OCPP queries."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class QueryResult:
    """Databricks SQL result with column names retained for row mapping."""

    columns: list[str]
    rows: list[tuple[Any, ...]]

    def as_dicts(self) -> list[dict[str, Any]]:
        return [dict(zip(self.columns, row)) for row in self.rows]


@dataclass(frozen=True)
class ChargingAttemptRecord:
    """Single row from the charging attempt view."""

    sso_id: str
    connector_id: int
    charging_attempt_start: dt.datetime
    charging_attempt_end: dt.datetime
    session_consumption_kwh: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class MergedChargingAttempt:
    """User-level charging attempt merged from adjacent attempt rows."""

    sso_id: str
    connector_id: int
    attempt_start: dt.datetime
    attempt_end: dt.datetime
    attempt_count: int
    total_consumption_kwh: float
    evse_id: str | None = None
    original_records: list[ChargingAttemptRecord] = field(default_factory=list)

    @property
    def duration_seconds(self) -> int:
        return int((self.attempt_end - self.attempt_start).total_seconds())

    @classmethod
    def from_records(
        cls,
        records: list[ChargingAttemptRecord],
        *,
        sso_id: str,
        connector_id: int,
        evse_id: str | None = None,
    ) -> MergedChargingAttempt:
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


@dataclass(frozen=True)
class OCPPEvent:
    """Single OCPP operation event from the warehouse."""

    sso_id: str
    operation_timestamp: dt.datetime
    ocpp_message_type: str
    ocpp_request_body: str | None = None
    ocpp_response_body: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OfflinePeriod:
    """Legacy-compatible Heartbeat gap that overlaps the requested window."""

    sso_id: str
    offline_start: dt.datetime
    offline_restore: dt.datetime
    duration_seconds: int
    reason: str
    evidence: dict[str, Any] = field(default_factory=dict)
