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
from mcp_datawarehouse.ocpp import OCPPSequenceQuery
from mcp_datawarehouse.settings import DatawarehouseSettings

logger = logging.getLogger(__name__)


async def query_charging_attempts(
    *,
    time_from: dt.datetime | str,
    time_to: dt.datetime | str,
    sso_id: str | None = None,
    evse_id: str | None = None,
    settings: DatawarehouseSettings | None = None,
) -> dict[str, Any]:
    """Return charging attempts and adjacent user-level merges for a device window."""

    try:
        async with DatabricksClient(settings or DatawarehouseSettings()) as client:
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
    return result


async def query_ocpp_sequence(
    *,
    sso_id: str,
    time_from: dt.datetime | str,
    time_to: dt.datetime | str,
    include_heartbeats: bool = False,
    include_raw_payload: bool = False,
    max_payload_chars: int = 1200,
    settings: DatawarehouseSettings | None = None,
) -> dict[str, Any]:
    """Return a compact OCPP event sequence for a device window."""

    try:
        async with DatabricksClient(settings or DatawarehouseSettings()) as client:
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
