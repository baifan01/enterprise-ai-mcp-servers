"""Business-level data warehouse service functions.

These async facades are the stable core entrypoints for Codex testing and future
MCP tools. They coordinate settings, Databricks client lifetime, query classes,
and safe failure conversion. SQL details stay in attempt/OCPP modules and
Databricks connector details stay in client.py.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

from mcp_datawarehouse.attempts import ChargingAttemptsQuery
from mcp_datawarehouse.client import DatabricksClient
from mcp_datawarehouse.errors import DatawarehouseServiceError
from mcp_datawarehouse.online_status import DeviceOnlineStatusQuery
from mcp_datawarehouse.ocpp import OCPPSequenceQuery
from mcp_datawarehouse.settings import DatawarehouseSettings

logger = logging.getLogger(__name__)


async def query_charging_attempts(
    *,
    time_from: dt.datetime | str,
    time_to: dt.datetime | str,
    sso_id: str | None = None,
    evse_id: str | None = None,
    user_id: str | None = None,
    settings: DatawarehouseSettings | None = None,
) -> dict[str, Any]:
    """Return charging attempts and adjacent user-level merges for a device window."""

    logger.info(
        "Starting data warehouse service request: kind=attempts sso_id=%s evse_id=%s "
        "time_from=%s time_to=%s has_user_id=%s",
        sso_id,
        evse_id,
        time_from,
        time_to,
        bool(user_id),
    )
    try:
        async with DatabricksClient(settings or DatawarehouseSettings(user_id=user_id)) as client:
            result = await ChargingAttemptsQuery(client).query(
                sso_id=sso_id,
                evse_id=evse_id,
                time_from=time_from,
                time_to=time_to,
            )
    except DatawarehouseServiceError as exc:
        return _failed_result(
            query={"sso_id": sso_id, "evse_id": evse_id, "time_from": time_from, "time_to": time_to},
            errors=[exc],
            kind="attempts",
        )
    except ValueError as exc:
        error = DatawarehouseServiceError(
            type="invalid_request",
            message=str(exc),
            segment="input",
            retryable=False,
        )
        return _failed_result(
            query={"sso_id": sso_id, "evse_id": evse_id, "time_from": time_from, "time_to": time_to},
            errors=[error],
            kind="attempts",
        )

    result["errors"] = []
    logger.info(
        "Completed data warehouse service request: kind=attempts raw_attempt_count=%s "
        "merged_attempt_count=%s",
        result.get("raw_attempt_count"),
        result.get("merged_attempt_count"),
    )
    return result


async def query_ocpp_sequence(
    *,
    sso_id: str,
    time_from: dt.datetime | str,
    time_to: dt.datetime | str,
    user_id: str | None = None,
    include_heartbeats: bool = False,
    include_raw_payload: bool = False,
    max_payload_chars: int = 1200,
    settings: DatawarehouseSettings | None = None,
) -> dict[str, Any]:
    """Return a compact OCPP event sequence for a device window."""

    logger.info(
        "Starting data warehouse service request: kind=ocpp sso_id=%s time_from=%s "
        "time_to=%s include_heartbeats=%s include_raw_payload=%s has_user_id=%s",
        sso_id,
        time_from,
        time_to,
        include_heartbeats,
        include_raw_payload,
        bool(user_id),
    )
    try:
        async with DatabricksClient(settings or DatawarehouseSettings(user_id=user_id)) as client:
            result = await OCPPSequenceQuery(client).query(
                sso_id=sso_id,
                time_from=time_from,
                time_to=time_to,
                include_heartbeats=include_heartbeats,
                include_raw_payload=include_raw_payload,
                max_payload_chars=max_payload_chars,
            )
    except DatawarehouseServiceError as exc:
        return _failed_result(
            query={
                "sso_id": sso_id,
                "time_from": time_from,
                "time_to": time_to,
                "include_heartbeats": include_heartbeats,
                "include_raw_payload": include_raw_payload,
                "max_payload_chars": max_payload_chars,
            },
            errors=[exc],
            kind="ocpp",
        )
    except ValueError as exc:
        error = DatawarehouseServiceError(
            type="invalid_request",
            message=str(exc),
            segment="input",
            retryable=False,
        )
        return _failed_result(
            query={
                "sso_id": sso_id,
                "time_from": time_from,
                "time_to": time_to,
                "include_heartbeats": include_heartbeats,
                "include_raw_payload": include_raw_payload,
                "max_payload_chars": max_payload_chars,
            },
            errors=[error],
            kind="ocpp",
        )

    result["errors"] = []
    logger.info(
        "Completed data warehouse service request: kind=ocpp event_count=%s",
        result.get("event_count"),
    )
    return result


async def query_device_online_status(
    *,
    sso_id: str,
    time_from: dt.datetime | str,
    time_to: dt.datetime | str,
    user_id: str | None = None,
    heartbeat_interval_seconds: int = 900,
    missed_heartbeat_tolerance: int = 1,
    recent_end_grace_seconds: int = 1800,
    settings: DatawarehouseSettings | None = None,
) -> dict[str, Any]:
    """Return legacy-compatible Heartbeat gap offline periods for a device window."""

    logger.info(
        "Starting data warehouse service request: kind=online_status sso_id=%s "
        "time_from=%s time_to=%s heartbeat_interval_seconds=%s "
        "missed_heartbeat_tolerance=%s recent_end_grace_seconds=%s has_user_id=%s",
        sso_id,
        time_from,
        time_to,
        heartbeat_interval_seconds,
        missed_heartbeat_tolerance,
        recent_end_grace_seconds,
        bool(user_id),
    )
    query = {
        "sso_id": sso_id,
        "time_from": time_from,
        "time_to": time_to,
        "heartbeat_interval_seconds": heartbeat_interval_seconds,
        "missed_heartbeat_tolerance": missed_heartbeat_tolerance,
        "recent_end_grace_seconds": recent_end_grace_seconds,
    }
    try:
        async with DatabricksClient(settings or DatawarehouseSettings(user_id=user_id)) as client:
            result = await DeviceOnlineStatusQuery(client).query(
                sso_id=sso_id,
                time_from=time_from,
                time_to=time_to,
                heartbeat_interval_seconds=heartbeat_interval_seconds,
                missed_heartbeat_tolerance=missed_heartbeat_tolerance,
                recent_end_grace_seconds=recent_end_grace_seconds,
            )
    except DatawarehouseServiceError as exc:
        return _failed_result(query=query, errors=[exc], kind="online_status")
    except ValueError as exc:
        error = DatawarehouseServiceError(
            type="invalid_request",
            message=str(exc),
            segment="input",
            retryable=False,
        )
        return _failed_result(query=query, errors=[error], kind="online_status")

    result["errors"] = []
    logger.info(
        "Completed data warehouse service request: kind=online_status has_offline=%s "
        "offline_period_count=%s event_count_in_window=%s heartbeat_count_in_window=%s",
        result.get("has_offline"),
        result.get("summary", {}).get("offline_period_count"),
        result.get("event_count_in_window"),
        result.get("heartbeat_count_in_window"),
    )
    return result


def _failed_result(
    *,
    query: dict[str, Any],
    errors: list[DatawarehouseServiceError],
    kind: str,
) -> dict[str, Any]:
    log_level = (
        logging.INFO
        if all(error.type == "invalid_request" for error in errors)
        else logging.WARNING
    )
    logger.log(
        log_level,
        "Data warehouse service request failed",
        extra={"kind": kind, "error_types": [error.type for error in errors]},
    )
    normalized_query = {key: _safe_json_value(value) for key, value in query.items()}
    if kind == "attempts":
        return {
            "query": normalized_query,
            "had_adjacent_merge": False,
            "raw_attempt_count": 0,
            "merged_attempt_count": 0,
            "raw_attempts": [],
            "merged_attempts": [],
            "errors": [error.to_dict() for error in errors],
        }
    if kind == "online_status":
        return {
            "query": normalized_query,
            "coverage": {
                "requested_time_from": normalized_query.get("time_from"),
                "requested_time_to": normalized_query.get("time_to"),
                "observed_time_from": None,
                "observed_time_to": None,
                "first_event_in_window": None,
                "last_event_in_window": None,
                "note": (
                    "Only events inside the requested range were queried. "
                    "Offline state before the first observed event or after the last observed "
                    "event is not inferred."
                ),
            },
            "has_offline": False,
            "offline_periods": [],
            "event_count_in_window": 0,
            "heartbeat_count_in_window": 0,
            "summary": {
                "offline_period_count": 0,
                "total_offline_seconds": 0,
                "total_offline_minutes": 0.0,
            },
            "errors": [error.to_dict() for error in errors],
        }
    return {
        "query": normalized_query,
        "event_count": 0,
        "event_type_counts": {},
        "events": [],
        "errors": [error.to_dict() for error in errors],
    }


def _safe_json_value(value: Any) -> Any:
    if isinstance(value, dt.datetime):
        return value.isoformat()
    return value
