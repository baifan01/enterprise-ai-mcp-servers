"""Driivz CPMS REST client."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

import httpx

from mcp_driivz.errors import DriivzServiceError
from mcp_driivz.settings import DriivzSettings


@dataclass(slots=True)
class ApiResult:
    method: str
    path: str
    status_code: int
    body: Any
    source_api: str

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    @property
    def request_id(self) -> str | None:
        if isinstance(self.body, dict):
            value = self.body.get("requestId")
            return value if isinstance(value, str) else None
        return None

    @property
    def count(self) -> int | None:
        if isinstance(self.body, dict):
            value = self.body.get("count")
            return value if isinstance(value, int) else None
        return None

    @property
    def data(self) -> Any:
        if isinstance(self.body, dict):
            return self.body.get("data")
        return None

    def to_segment(self) -> dict[str, Any]:
        return {
            "source_api": self.source_api,
            "request_id": self.request_id,
            "count": self.count,
            "data": self.data,
        }


class DriivzClient:
    """Thin async REST client with turn-local dmsTicket caching."""

    def __init__(self, settings: DriivzSettings) -> None:
        self._settings = settings
        self._ticket: str | None = None
        self._client = httpx.AsyncClient(
            base_url=settings.base_url.rstrip("/"),
            timeout=settings.timeout_seconds,
            follow_redirects=True,
            headers={"Accept": "application/json"},
        )

    async def __aenter__(self) -> DriivzClient:
        await self.login()
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def login(self) -> None:
        if self._ticket:
            return
        try:
            self._settings.validate_auth()
        except ValueError as exc:
            raise DriivzServiceError(
                type="auth_failed",
                message=str(exc),
                segment="auth",
                source_api="POST /v1/authentication/operator/login",
                retryable=False,
            ) from exc
        response = await self._client.post(
            "/v1/authentication/operator/login",
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            content=json.dumps(
                {
                    "password": self._settings.password.get_secret_value()
                    if self._settings.password
                    else "",
                    "userName": self._settings.username,
                },
                ensure_ascii=False,
            ).encode("utf-8"),
        )
        body = _parse_response_body(response)
        if response.status_code >= 400:
            raise DriivzServiceError(
                type="auth_failed",
                message=f"Driivz login failed: {_safe_error_message(body)}",
                segment="auth",
                source_api="POST /v1/authentication/operator/login",
                http_status=response.status_code,
                request_id=_request_id(body),
                retryable=False,
            )
        ticket = _find_first_key(body, "ticket")
        if not isinstance(ticket, str) or not ticket:
            raise DriivzServiceError(
                type="invalid_response",
                message="Driivz login response did not include a ticket.",
                segment="auth",
                source_api="POST /v1/authentication/operator/login",
                http_status=response.status_code,
                request_id=_request_id(body),
                retryable=False,
            )
        self._ticket = _validate_header_value("dmsTicket", ticket)
        self._client.headers["dmsTicket"] = self._ticket

    async def get_json(self, path: str, *, source_api: str | None = None) -> ApiResult:
        return await self._request("GET", path, source_api=source_api)

    async def post_json(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        source_api: str | None = None,
    ) -> ApiResult:
        return await self._request(
            "POST",
            path,
            params=params,
            json=body or {},
            source_api=source_api,
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        source_api: str | None,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> ApiResult:
        await self.login()
        attempts = 3
        for attempt in range(1, attempts + 1):
            try:
                response = await self._client.request(
                    method,
                    path,
                    params=params,
                    json=json,
                )
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError) as exc:
                if attempt == attempts:
                    raise DriivzServiceError(
                        type="timeout" if isinstance(exc, httpx.ReadTimeout) else "rest_error",
                        message=f"Driivz REST request failed: {type(exc).__name__}",
                        source_api=source_api or f"{method} {path}",
                        retryable=True,
                    ) from exc
                await asyncio.sleep(0.2 * attempt)
                continue

            body = _parse_response_body(response)
            result = ApiResult(
                method=method,
                path=path,
                status_code=response.status_code,
                body=body,
                source_api=source_api or f"{method} {path}",
            )
            if response.status_code >= 500 and attempt < attempts:
                await asyncio.sleep(0.2 * attempt)
                continue
            return result
        raise AssertionError("unreachable")


def result_to_error(
    result: ApiResult,
    *,
    segment: str,
    error_type: str | None = None,
    message: str | None = None,
) -> DriivzServiceError:
    inferred_type = error_type or ("auth_failed" if _is_invalid_ticket(result.body) else "rest_error")
    return DriivzServiceError(
        type=inferred_type,
        message=message or f"Driivz REST request failed: {_safe_error_message(result.body)}",
        segment=segment,
        source_api=result.source_api,
        http_status=result.status_code,
        request_id=result.request_id,
        retryable=False,
    )


def _parse_response_body(response: httpx.Response) -> Any:
    try:
        return response.json()
    except json.JSONDecodeError:
        return {"raw_text_preview": response.text[:500]}


def _find_first_key(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        if key in value:
            return value[key]
        for child in value.values():
            found = _find_first_key(child, key)
            if found is not None:
                return found
    if isinstance(value, list):
        for child in value:
            found = _find_first_key(child, key)
            if found is not None:
                return found
    return None


def _request_id(value: Any) -> str | None:
    if isinstance(value, dict):
        request_id = value.get("requestId")
        return request_id if isinstance(request_id, str) else None
    return None


def _is_invalid_ticket(value: Any) -> bool:
    text = json.dumps(value, ensure_ascii=False, default=str).lower()
    return "invalid.ticket" in text


def _safe_error_message(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("message", "reason", "code"):
            item = value.get(key)
            if isinstance(item, str) and item:
                return item[:300]
        errors = value.get("errors")
        if isinstance(errors, list) and errors:
            first = errors[0]
            if isinstance(first, dict):
                item = first.get("message") or first.get("reason") or first.get("code")
                if isinstance(item, str) and item:
                    return item[:300]
    return "unexpected response"


def _validate_header_value(name: str, value: str) -> str:
    try:
        value.encode("ascii")
    except UnicodeEncodeError as exc:
        raise DriivzServiceError(
            type="auth_failed",
            message=f"{name} contains non-ASCII characters and cannot be sent as an HTTP header.",
            segment="auth",
            retryable=False,
        ) from exc
    return value
