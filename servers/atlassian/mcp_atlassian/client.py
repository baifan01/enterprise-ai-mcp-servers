"""Thin async Atlassian REST client."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx

from mcp_atlassian.errors import AtlassianServiceError
from mcp_atlassian.settings import AtlassianSettings


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


class AtlassianClient:
    """Thin async REST client with basic auth and JSON helpers."""

    def __init__(self, settings: AtlassianSettings) -> None:
        try:
            settings.validate_auth()
        except ValueError as exc:
            raise AtlassianServiceError(
                type="auth_failed",
                message=str(exc),
                segment="auth",
                retryable=False,
            ) from exc
        self._base_url = (settings.base_url or "").rstrip("/")
        token = settings.api_token.get_secret_value() if settings.api_token else ""
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=settings.timeout_seconds,
            follow_redirects=True,
            auth=(settings.email or "", token),
            headers={"Accept": "application/json"},
        )

    @property
    def base_url(self) -> str:
        return self._base_url

    async def __aenter__(self) -> "AtlassianClient":
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get_json(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        source_api: str | None = None,
    ) -> ApiResult:
        return await self._request("GET", path, params=params, source_api=source_api)

    async def post_json(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | list[Any] | None = None,
        source_api: str | None = None,
    ) -> ApiResult:
        return await self._request("POST", path, params=params, json=body, source_api=source_api)

    async def put_json(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | list[Any] | None = None,
        source_api: str | None = None,
    ) -> ApiResult:
        return await self._request("PUT", path, params=params, json=body, source_api=source_api)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        source_api: str | None,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | list[Any] | None = None,
    ) -> ApiResult:
        try:
            response = await self._client.request(method, path, params=params, json=json)
        except httpx.TimeoutException as exc:
            raise AtlassianServiceError(
                type="timeout",
                message=f"Atlassian REST request timed out: {method} {path}",
                source_api=source_api or f"{method} {path}",
                retryable=True,
            ) from exc
        except httpx.HTTPError as exc:
            raise AtlassianServiceError(
                type="rest_error",
                message=f"Atlassian REST request failed: {type(exc).__name__}",
                source_api=source_api or f"{method} {path}",
                retryable=True,
            ) from exc

        body = _parse_response_body(response)
        result = ApiResult(
            method=method,
            path=path,
            status_code=response.status_code,
            body=body,
            source_api=source_api or f"{method} {path}",
        )
        if response.status_code >= 400:
            raise AtlassianServiceError(
                type="auth_failed" if response.status_code in {401, 403} else "rest_error",
                message=f"Atlassian REST request failed: {_safe_error_message(body)}",
                source_api=result.source_api,
                http_status=response.status_code,
                retryable=response.status_code >= 500,
            )
        return result


def _parse_response_body(response: httpx.Response) -> Any:
    try:
        return response.json()
    except json.JSONDecodeError:
        return {"raw_text_preview": response.text[:500]}


def _safe_error_message(value: Any) -> str:
    if isinstance(value, dict):
        if isinstance(value.get("message"), str):
            return value["message"][:500]
        messages = value.get("errorMessages")
        if isinstance(messages, list) and messages:
            return "; ".join(str(item) for item in messages)[:500]
    return str(value)[:500]
