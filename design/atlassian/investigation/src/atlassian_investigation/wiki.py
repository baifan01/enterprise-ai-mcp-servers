"""Confluence wiki search investigation APIs.

This module mirrors the Jira ticket search boundary: callers provide structured
conditions, while the investigation service owns Confluence API paths and CQL
construction. It deliberately avoids exposing arbitrary CQL to agents.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from .client import AtlassianClient

DEFAULT_WIKI_SEARCH_EXPAND = [
    "content.space",
    "content.version",
]

_SPACE_KEY_PATTERN = re.compile(r"^[A-Z][A-Z0-9_~-]*$")
_SEARCH_FIELDS = {"text", "title"}
_CONTENT_TYPES = {"page", "blogpost", "comment", "attachment"}


class WikiSearchService:
    """Business-shaped Confluence wiki queries for Atlassian API investigation."""

    def __init__(self, client: AtlassianClient) -> None:
        self.client = client

    def search_wiki(
        self,
        *,
        text: str | Iterable[str] | None = None,
        search_field: str = "text",
        space_keys: list[str] | None = None,
        content_types: list[str] | None = None,
        match: str = "all",
        max_results: int = 10,
        expand: list[str] | None = None,
    ) -> dict[str, Any]:
        """Search Confluence content with a controlled CQL builder."""

        normalized_text = _normalize_text(text)
        normalized_search_field = _normalize_search_field(search_field)
        normalized_spaces = _normalize_space_keys(space_keys or [])
        normalized_content_types = _normalize_content_types(content_types or ["page"])
        normalized_match = _normalize_match(match)
        bounded_max_results = _bounded_max_results(max_results)
        selected_expand = expand if expand is not None else DEFAULT_WIKI_SEARCH_EXPAND
        cql = _build_structured_cql(
            normalized_text,
            search_field=normalized_search_field,
            space_keys=normalized_spaces,
            content_types=normalized_content_types,
            match=normalized_match,
        )

        response = self.client.get_json(
            "/wiki/rest/api/search",
            query={
                "cql": cql,
                "limit": bounded_max_results,
                "expand": selected_expand,
            },
        )
        results = response.data.get("results")
        result_count = len(results) if isinstance(results, list) else 0
        return {
            "source_api": "GET /wiki/rest/api/search",
            "query": {
                "text": normalized_text,
                "search_field": normalized_search_field,
                "space_keys": normalized_spaces,
                "content_types": normalized_content_types,
                "match": normalized_match,
                "max_results": bounded_max_results,
                "expand": selected_expand,
                "cql": cql,
            },
            "status_code": response.status_code,
            "result_count": result_count,
            "data": response.data,
        }


def _normalize_text(text: str | Iterable[str] | None) -> list[str]:
    if text is None:
        return []
    if isinstance(text, str):
        values = [text]
    else:
        values = list(text)
    normalized = [value.strip() for value in values if value and value.strip()]
    if len(normalized) > 8:
        raise ValueError("At most 8 wiki search terms are allowed.")
    too_long = [value for value in normalized if len(value) > 120]
    if too_long:
        raise ValueError("Each wiki search term must be 120 characters or fewer.")
    return normalized


def _normalize_search_field(search_field: str) -> str:
    normalized = search_field.strip().lower()
    if normalized not in _SEARCH_FIELDS:
        allowed = ", ".join(sorted(_SEARCH_FIELDS))
        raise ValueError(f"search_field must be one of: {allowed}.")
    return normalized


def _normalize_space_keys(space_keys: Iterable[str]) -> list[str]:
    normalized = [space.strip().upper() for space in space_keys if space and space.strip()]
    invalid = [space for space in normalized if not _SPACE_KEY_PATTERN.fullmatch(space)]
    if invalid:
        raise ValueError(f"Invalid Confluence space key(s): {', '.join(invalid)}")
    return normalized


def _normalize_content_types(content_types: Iterable[str]) -> list[str]:
    normalized = [content_type.strip().lower() for content_type in content_types if content_type.strip()]
    if not normalized:
        raise ValueError("At least one content type is required.")
    invalid = [content_type for content_type in normalized if content_type not in _CONTENT_TYPES]
    if invalid:
        allowed = ", ".join(sorted(_CONTENT_TYPES))
        raise ValueError(f"Invalid content type(s): {', '.join(invalid)}. Allowed: {allowed}.")
    return normalized


def _normalize_match(match: str) -> str:
    normalized = match.strip().lower()
    if normalized not in {"all", "any"}:
        raise ValueError("match must be either 'all' or 'any'.")
    return normalized


def _bounded_max_results(value: int) -> int:
    if value <= 0:
        raise ValueError("max_results must be positive.")
    return min(value, 50)


def _build_structured_cql(
    text: list[str],
    *,
    search_field: str,
    space_keys: list[str],
    content_types: list[str],
    match: str,
) -> str:
    clauses: list[str] = []
    if content_types:
        clauses.append(_build_in_clause("type", content_types))
    if space_keys:
        clauses.append(_build_in_clause("space", space_keys))
    if text:
        clauses.append(_build_text_clause(text, search_field=search_field, match=match))
    if not clauses:
        raise ValueError("At least one wiki search condition is required.")
    return " AND ".join(clauses) + " ORDER BY lastmodified DESC"


def _build_text_clause(text: list[str], *, search_field: str, match: str) -> str:
    operator = " AND " if match == "all" else " OR "
    text_clause = operator.join(
        f'{search_field} ~ "{_escape_cql_string(value)}"' for value in text
    )
    return f"({text_clause})"


def _build_in_clause(field_name: str, values: list[str]) -> str:
    quoted_values = ", ".join(f'"{_escape_cql_string(value)}"' for value in values)
    return f"{field_name} in ({quoted_values})"


def _escape_cql_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
