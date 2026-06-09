"""Jira ticket read/search investigation APIs.

This module intentionally exposes narrow methods instead of arbitrary JQL. That
keeps the investigation close to the future local tool contract: agents provide
keywords or an issue key, while this module owns API paths and JQL construction.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from .client import AtlassianClient

DEFAULT_TICKET_FIELDS = [
    "summary",
    "status",
    "issuetype",
    "project",
    "priority",
    "assignee",
    "reporter",
    "created",
    "updated",
    "labels",
    "components",
    "parent",
    "subtasks",
    "description",
    "comment",
    "attachment",
]

DEFAULT_SEARCH_FIELDS = [
    "summary",
    "status",
    "issuetype",
    "project",
    "priority",
    "assignee",
    "reporter",
    "created",
    "updated",
    "labels",
    "parent",
]

_PROJECT_KEY_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]+$")
_ISSUE_KEY_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]+-\d+$")
_TEXT_FIELDS = {"text", "summary", "description"}


class TicketQueryService:
    """Business-shaped Jira ticket queries for Atlassian API investigation."""

    def __init__(self, client: AtlassianClient) -> None:
        self.client = client

    def get_ticket(
        self,
        issue_key: str,
        *,
        fields: list[str] | None = None,
        expand: list[str] | None = None,
    ) -> dict[str, Any]:
        """Read one Jira ticket by issue key."""

        normalized_issue_key = _normalize_issue_key(issue_key)
        selected_fields = fields or DEFAULT_TICKET_FIELDS
        response = self.client.get_json(
            f"/rest/api/3/issue/{normalized_issue_key}",
            query={
                "fields": selected_fields,
                "expand": expand,
            },
        )
        return {
            "source_api": f"GET /rest/api/3/issue/{normalized_issue_key}",
            "issue_key": normalized_issue_key,
            "status_code": response.status_code,
            "data": response.data,
        }

    def search_tickets(
        self,
        *,
        text: str | Iterable[str] | None = None,
        text_field: str = "text",
        project_keys: list[str] | None = None,
        creators: list[str] | None = None,
        assignees: list[str] | None = None,
        statuses: list[str] | None = None,
        issue_types: list[str] | None = None,
        match: str = "all",
        max_results: int = 20,
        fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """Search Jira tickets with a controlled structured JQL builder."""

        normalized_keywords = _normalize_text(text)
        normalized_text_field = _normalize_text_field(text_field)
        normalized_projects = _normalize_project_keys(project_keys or [])
        normalized_creators = _normalize_field_values(creators or [], field_name="creators")
        normalized_assignees = _normalize_field_values(assignees or [], field_name="assignees")
        normalized_statuses = _normalize_field_values(statuses or [], field_name="statuses")
        normalized_issue_types = _normalize_field_values(issue_types or [], field_name="issue_types")
        normalized_match = _normalize_match(match)
        bounded_max_results = _bounded_max_results(max_results)
        selected_fields = fields or DEFAULT_SEARCH_FIELDS
        jql = _build_structured_jql(
            normalized_keywords,
            text_field=normalized_text_field,
            project_keys=normalized_projects,
            creators=normalized_creators,
            assignees=normalized_assignees,
            statuses=normalized_statuses,
            issue_types=normalized_issue_types,
            match=normalized_match,
        )

        response = self.client.get_json(
            "/rest/api/3/search/jql",
            query={
                "jql": jql,
                "maxResults": bounded_max_results,
                "fields": selected_fields,
            },
        )
        issues = response.data.get("issues")
        issue_count = len(issues) if isinstance(issues, list) else 0
        return {
            "source_api": "GET /rest/api/3/search/jql",
            "query": {
                "text": normalized_keywords,
                "text_field": normalized_text_field,
                "project_keys": normalized_projects,
                "creators": normalized_creators,
                "assignees": normalized_assignees,
                "statuses": normalized_statuses,
                "issue_types": normalized_issue_types,
                "match": normalized_match,
                "max_results": bounded_max_results,
                "fields": selected_fields,
                "jql": jql,
            },
            "status_code": response.status_code,
            "issue_count": issue_count,
            "data": response.data,
        }


def _normalize_issue_key(issue_key: str) -> str:
    normalized = issue_key.strip().upper()
    if not _ISSUE_KEY_PATTERN.fullmatch(normalized):
        raise ValueError("issue_key must look like PROJECT-123.")
    return normalized


def _normalize_keywords(keywords: Iterable[str]) -> list[str]:
    normalized = [keyword.strip() for keyword in keywords if keyword and keyword.strip()]
    if len(normalized) > 8:
        raise ValueError("At most 8 keywords are allowed for one investigation query.")
    too_long = [keyword for keyword in normalized if len(keyword) > 80]
    if too_long:
        raise ValueError("Each keyword must be 80 characters or fewer.")
    return normalized


def _normalize_text(text: str | Iterable[str] | None) -> list[str]:
    if text is None:
        return []
    if isinstance(text, str):
        return _normalize_keywords([text])
    return _normalize_keywords(text)


def _normalize_text_field(text_field: str) -> str:
    normalized = text_field.strip().lower()
    if normalized not in _TEXT_FIELDS:
        allowed = ", ".join(sorted(_TEXT_FIELDS))
        raise ValueError(f"text_field must be one of: {allowed}.")
    return normalized


def _normalize_project_keys(project_keys: Iterable[str]) -> list[str]:
    normalized = [project.strip().upper() for project in project_keys if project.strip()]
    invalid = [project for project in normalized if not _PROJECT_KEY_PATTERN.fullmatch(project)]
    if invalid:
        raise ValueError(f"Invalid Jira project key(s): {', '.join(invalid)}")
    return normalized


def _normalize_field_values(values: Iterable[str], *, field_name: str) -> list[str]:
    normalized = [value.strip() for value in values if value and value.strip()]
    if len(normalized) > 20:
        raise ValueError(f"At most 20 {field_name} values are allowed.")
    too_long = [value for value in normalized if len(value) > 120]
    if too_long:
        raise ValueError(f"Each {field_name} value must be 120 characters or fewer.")
    return normalized


def _normalize_match(match: str) -> str:
    normalized = match.strip().lower()
    if normalized not in {"all", "any"}:
        raise ValueError("match must be either 'all' or 'any'.")
    return normalized


def _bounded_max_results(value: int) -> int:
    if value <= 0:
        raise ValueError("max_results must be positive.")
    return min(value, 100)


def _build_structured_jql(
    keywords: list[str],
    *,
    text_field: str,
    project_keys: list[str],
    creators: list[str],
    assignees: list[str],
    statuses: list[str],
    issue_types: list[str],
    match: str,
) -> str:
    clauses: list[str] = []
    if project_keys:
        projects = ", ".join(project_keys)
        clauses.append(f"project in ({projects})")
    if creators:
        clauses.append(_build_in_clause("creator", creators))
    if assignees:
        clauses.append(_build_in_clause("assignee", assignees))
    if statuses:
        clauses.append(_build_in_clause("status", statuses))
    if issue_types:
        clauses.append(_build_in_clause("issuetype", issue_types))
    if keywords:
        clauses.append(_build_text_clause(keywords, text_field=text_field, match=match))
    if not clauses:
        raise ValueError("At least one search condition is required.")
    return " AND ".join(clauses) + " ORDER BY updated DESC"


def _build_text_clause(keywords: list[str], *, text_field: str, match: str) -> str:
    operator = " AND " if match == "all" else " OR "
    keyword_clause = operator.join(
        f'{text_field} ~ "{_escape_jql_string(keyword)}"' for keyword in keywords
    )
    return f"({keyword_clause})"


def _build_in_clause(field_name: str, values: list[str]) -> str:
    quoted_values = ", ".join(f'"{_escape_jql_string(value)}"' for value in values)
    return f"{field_name} in ({quoted_values})"


def _escape_jql_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
