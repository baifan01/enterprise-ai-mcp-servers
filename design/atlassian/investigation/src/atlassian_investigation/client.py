"""Small Atlassian Cloud REST client used by investigation code."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .config import AtlassianSettings


class AtlassianClientError(Exception):
    """Raised when an Atlassian API request fails."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class ApiResponse:
    """Minimal API response wrapper for investigation output."""

    method: str
    path: str
    status_code: int
    data: dict[str, Any]


class AtlassianClient:
    """Authenticated JSON client for Jira investigation endpoints."""

    def __init__(self, settings: AtlassianSettings) -> None:
        self.settings = settings

    @classmethod
    def from_env(cls, env_file: str | None = None) -> "AtlassianClient":
        """Create a client from an investigation `.env` file."""

        return cls(AtlassianSettings.from_env(env_file=env_file))

    def get_json(
        self,
        path: str,
        *,
        query: Mapping[str, Any] | None = None,
    ) -> ApiResponse:
        """Execute a GET request and return parsed JSON."""

        return self._request_json("GET", path, query=query)

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, Any] | None = None,
    ) -> ApiResponse:
        url = self._build_url(path, query=query)
        request = Request(url, headers=self._headers(), method=method)
        try:
            with urlopen(request, timeout=self.settings.timeout_seconds) as response:
                raw_text = response.read().decode("utf-8")
                data = json.loads(raw_text) if raw_text else {}
                return ApiResponse(
                    method=method,
                    path=path,
                    status_code=response.status,
                    data=data,
                )
        except HTTPError as exc:
            raise self._http_error(exc) from exc
        except URLError as exc:
            raise AtlassianClientError(f"Network error while calling Atlassian: {exc}") from exc

    def _build_url(self, path: str, *, query: Mapping[str, Any] | None = None) -> str:
        if not query:
            return f"{self.settings.base_url}{path}"
        flattened: dict[str, str] = {}
        for key, value in query.items():
            if value is None:
                continue
            if isinstance(value, (list, tuple)):
                flattened[key] = ",".join(str(item) for item in value)
            else:
                flattened[key] = str(value)
        query_string = urlencode(flattened)
        return f"{self.settings.base_url}{path}?{query_string}"

    def _headers(self) -> dict[str, str]:
        auth = base64.b64encode(
            f"{self.settings.email}:{self.settings.api_token}".encode("utf-8")
        ).decode("utf-8")
        return {
            "Accept": "application/json",
            "Authorization": f"Basic {auth}",
        }

    def _http_error(self, exc: HTTPError) -> AtlassianClientError:
        raw_body = exc.read().decode("utf-8", errors="replace")
        return AtlassianClientError(
            f"Atlassian API error {exc.code}: {_extract_error_message(raw_body)}",
            status_code=exc.code,
        )


def _extract_error_message(raw_body: str) -> str:
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        return raw_body[:500]

    messages = payload.get("errorMessages") or []
    if messages:
        return "; ".join(str(message) for message in messages)
    errors = payload.get("errors") or {}
    if errors:
        return "; ".join(f"{key}: {value}" for key, value in errors.items())
    return raw_body[:500]
