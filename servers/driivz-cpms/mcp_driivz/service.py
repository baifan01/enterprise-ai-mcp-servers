"""Business-level Driivz CPMS service functions."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from mcp_driivz.client import ApiResult, DriivzClient, result_to_error
from mcp_driivz.errors import DriivzServiceError
from mcp_driivz.settings import DriivzSettings

PROFILE_API = "POST /v1/chargers/profiles/filter"
LOCATION_API = "POST /v1/chargers/locations/filter"
SITE_API = "GET /v1/sites/{siteId}"
SITE_PROGRAM_API = "GET /v1/companies/{site.companyId}"
STATUS_API = "POST /v1/chargers/statuses/filter"
RECENT_SESSIONS_API = "POST /v1/ev-transactions/chargers/{identityKey}/filter"


async def review_site_runtime_by_device(
    device_id: str,
    *,
    include_recent_sessions: bool = True,
    settings: DriivzSettings | None = None,
) -> dict[str, Any]:
    """Return the first-version Driivz site runtime review JSON."""

    normalized_device_id = device_id.strip()
    if not normalized_device_id:
        error = DriivzServiceError(
            type="invalid_request",
            message="device_id must not be empty.",
            segment="input",
            retryable=False,
        )
        return _base_result(device_id=device_id, resolved=False, errors=[error])

    try:
        async with DriivzClient(settings or DriivzSettings()) as client:
            return await _review_with_client(
                client,
                normalized_device_id,
                include_recent_sessions=include_recent_sessions,
            )
    except DriivzServiceError as exc:
        return _base_result(device_id=device_id, resolved=False, errors=[exc])


async def _review_with_client(
    client: DriivzClient,
    device_id: str,
    *,
    include_recent_sessions: bool,
) -> dict[str, Any]:
    errors: list[DriivzServiceError] = []
    try:
        profile = await client.post_json(
            "/v1/chargers/profiles/filter",
            params={"pageSize": 20, "pageNumber": 0},
            body={"identityKey": device_id},
            source_api=PROFILE_API,
        )
    except DriivzServiceError as exc:
        exc.segment = exc.segment or "profile"
        return _base_result(device_id=device_id, resolved=False, errors=[exc])

    if not profile.ok:
        error = result_to_error(profile, segment="profile")
        return _base_result(
            device_id=device_id,
            resolved=False,
            profile=_segment_with_error(profile, error),
            errors=[error],
        )

    profile_data = _as_list(profile.data)
    if len(profile_data) == 0:
        error = DriivzServiceError(
            type="not_found",
            message="No charger profile found for device_id.",
            segment="profile",
            source_api=PROFILE_API,
            http_status=profile.status_code,
            request_id=profile.request_id,
            retryable=False,
        )
        return _base_result(
            device_id=device_id,
            resolved=False,
            profile=_segment_with_error(profile, error),
            errors=[error],
        )
    if len(profile_data) > 1:
        error = DriivzServiceError(
            type="ambiguous_result",
            message="Multiple charger profiles found for device_id.",
            segment="profile",
            source_api=PROFILE_API,
            http_status=profile.status_code,
            request_id=profile.request_id,
            retryable=False,
        )
        return _base_result(
            device_id=device_id,
            resolved=False,
            profile=_segment_with_error(profile, error),
            errors=[error],
        )

    charger = profile_data[0]
    charger_id = charger.get("id") if isinstance(charger, dict) else None
    site_id = charger.get("siteId") if isinstance(charger, dict) else None

    tasks: dict[str, asyncio.Task[ApiResult | None]] = {}
    if isinstance(site_id, int):
        tasks["site"] = asyncio.create_task(
            client.get_json(f"/v1/sites/{site_id}", source_api=SITE_API)
        )
    if isinstance(charger_id, int):
        tasks["location"] = asyncio.create_task(
            client.post_json(
                "/v1/chargers/locations/filter",
                params={"pageSize": 20, "pageNumber": 0},
                body={"ids": [charger_id]},
                source_api=LOCATION_API,
            )
        )
        tasks["status"] = asyncio.create_task(
            client.post_json(
                "/v1/chargers/statuses/filter",
                params={"pageSize": 20, "pageNumber": 0},
                body={"ids": [charger_id]},
                source_api=STATUS_API,
            )
        )
    if include_recent_sessions:
        tasks["recent_sessions"] = asyncio.create_task(
            _fetch_recent_sessions(client, device_id)
        )

    segments: dict[str, Any] = {
        "profile": profile.to_segment(),
        "location": None,
        "site": None,
        "site_program": None,
        "status": None,
        "recent_sessions": None,
    }

    completed = await _collect_segments(tasks, errors)
    segments.update(completed)

    site_segment = segments.get("site")
    company_id = _extract_company_id(site_segment)
    if company_id is not None:
        try:
            site_program = await client.get_json(
                f"/v1/companies/{company_id}",
                source_api=SITE_PROGRAM_API,
            )
            if site_program.ok:
                segments["site_program"] = site_program.to_segment()
            else:
                error = result_to_error(site_program, segment="site_program")
                errors.append(error)
                segments["site_program"] = _segment_with_error(site_program, error)
        except DriivzServiceError as exc:
            exc.segment = exc.segment or "site_program"
            errors.append(exc)
            segments["site_program"] = _error_segment(SITE_PROGRAM_API, exc)

    return {
        "device_id": device_id,
        "resolved": True,
        **segments,
        "errors": [error.to_dict() for error in errors],
    }


async def _fetch_recent_sessions(client: DriivzClient, device_id: str) -> ApiResult:
    until = datetime.now(UTC)
    since = until - timedelta(days=7)
    return await client.post_json(
        f"/v1/ev-transactions/chargers/{device_id}/filter",
        params={"pageSize": 20, "pageNumber": 0, "sortBy": "id:desc"},
        body={
            "fromDate": _format_utc(since),
            "toDate": _format_utc(until),
            "transactionBillingStatus": "FINAL_COST",
        },
        source_api=RECENT_SESSIONS_API,
    )


async def _collect_segments(
    tasks: dict[str, asyncio.Task[ApiResult | None]],
    errors: list[DriivzServiceError],
) -> dict[str, Any]:
    # Keep this bounded; current design permits at most site, location, status, and sessions.
    output: dict[str, Any] = {}
    for segment, task in tasks.items():
        try:
            result = await task
        except DriivzServiceError as exc:
            exc.segment = exc.segment or segment
            errors.append(exc)
            output[segment] = _error_segment(_source_api_for_segment(segment), exc)
            continue
        if result is None:
            output[segment] = None
        elif result.ok:
            item = result.to_segment()
            if segment == "recent_sessions":
                item["window_days"] = 7
            output[segment] = item
        else:
            error = result_to_error(result, segment=segment)
            errors.append(error)
            output[segment] = _segment_with_error(result, error)
    return output


def _base_result(
    *,
    device_id: str,
    resolved: bool,
    errors: list[DriivzServiceError],
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "device_id": device_id,
        "resolved": resolved,
        "profile": profile,
        "location": None,
        "site": None,
        "site_program": None,
        "status": None,
        "recent_sessions": None,
        "errors": [error.to_dict() for error in errors],
    }


def _segment_with_error(result: ApiResult, error: DriivzServiceError) -> dict[str, Any]:
    segment = result.to_segment()
    segment["error"] = error.to_dict()
    return segment


def _error_segment(source_api: str, error: DriivzServiceError) -> dict[str, Any]:
    return {
        "source_api": source_api,
        "request_id": error.request_id,
        "count": None,
        "data": None,
        "error": error.to_dict(),
    }


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _extract_company_id(site_segment: Any) -> int | None:
    if not isinstance(site_segment, dict):
        return None
    data = site_segment.get("data")
    site = data[0] if isinstance(data, list) and data else data
    if isinstance(site, dict) and isinstance(site.get("companyId"), int):
        return site["companyId"]
    return None


def _format_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _source_api_for_segment(segment: str) -> str:
    return {
        "profile": PROFILE_API,
        "location": LOCATION_API,
        "site": SITE_API,
        "site_program": SITE_PROGRAM_API,
        "status": STATUS_API,
        "recent_sessions": RECENT_SESSIONS_API,
    }.get(segment, "unknown")
