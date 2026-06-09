"""Confluence wiki page adapter for structured local-tool operations."""

from __future__ import annotations

import re
from typing import Any, Iterable
from urllib.parse import parse_qs, urlparse

from mcp_atlassian.client import AtlassianClient
from mcp_atlassian.errors import AtlassianServiceError
from mcp_atlassian.markdown_storage import (
    markdown_to_storage,
    with_ai_generated_notice,
)

AI_GENERATED_LABEL = "ubitricity-ai-generated"
AGENT_FRIENDLY_LABEL = "ubitricity-agent-friendly"


class WikiService:
    """Confluence wiki API operations using structured inputs only."""

    def __init__(self, client: AtlassianClient) -> None:
        self._client = client
        self._base_url = getattr(client, "base_url", None)

    async def read_page(
        self,
        *,
        page_id: str | None = None,
        page_url: str | None = None,
        include_footer_comments: bool = False,
    ) -> dict[str, Any]:
        resolved_page_id = resolve_page_id(page_id=page_id, page_url=page_url)
        page = await self._get_page(resolved_page_id)
        return await self._normalize_page(
            page,
            include_footer_comments=include_footer_comments,
        )

    async def search_pages(
        self,
        *,
        text: str | Iterable[str] | None = None,
        search_field: str = "text",
        parent_url: str | None = None,
        agent_friendly_only: bool = False,
        match: str = "all",
        max_results: int = 10,
    ) -> dict[str, Any]:
        terms = _normalize_text(text)
        normalized_field = _normalize_search_field(search_field)
        normalized_match = _normalize_match(match)
        limit = _bounded_max_results(max_results)
        parent_id = resolve_parent_id(parent_url=parent_url) if parent_url else None
        cql = _build_search_cql(
            terms=terms,
            search_field=normalized_field,
            parent_id=parent_id,
            agent_friendly_only=agent_friendly_only,
            match=normalized_match,
        )
        result = await self._client.get_json(
            "/wiki/rest/api/search",
            params={"cql": cql, "limit": limit},
            source_api="GET /wiki/rest/api/search",
        )
        body = result.body if isinstance(result.body, dict) else {}
        items = [
            _normalize_search_result(item, base_url=self._base_url)
            for item in _as_list(body.get("results"))
        ]
        warnings: list[dict[str, Any]] = []
        if parent_id:
            parent_item = await self._matching_parent_search_item(
                parent_id=parent_id,
                terms=terms,
                search_field=normalized_field,
                match=normalized_match,
                warnings=warnings,
            )
            if parent_item is not None:
                items = [parent_item, *items]
        deduped = _dedupe_search_items(items)[:limit]
        return {
            "query": {
                "text": terms,
                "search_field": normalized_field,
                "parent_url": parent_url,
                "parent_id": parent_id,
                "agent_friendly_only": agent_friendly_only,
                "match": normalized_match,
                "max_results": limit,
                "cql": cql,
            },
            "result_count": len(deduped),
            "results": deduped,
            "warnings": warnings,
            "errors": [],
        }

    async def create_child_page(
        self,
        *,
        parent_url: str,
        title: str,
        body_markdown: str,
        mark_agent_friendly: bool = False,
    ) -> dict[str, Any]:
        parent_ref = await self._resolve_parent(parent_url=parent_url)
        normalized_title = title.strip()
        if not normalized_title:
            raise AtlassianServiceError(
                type="invalid_request",
                message="title must not be empty.",
                segment="input",
                retryable=False,
            )
        converted = markdown_to_storage(body_markdown)
        storage_value = with_ai_generated_notice(converted.value)
        result = await self._client.post_json(
            "/wiki/api/v2/pages",
            body={
                "spaceId": parent_ref["space_id"],
                "status": "current",
                "title": normalized_title,
                "parentId": parent_ref["id"],
                "body": {"representation": "storage", "value": storage_value},
            },
            source_api="POST /wiki/api/v2/pages",
        )
        created = result.body if isinstance(result.body, dict) else {}
        warnings = [warning.to_dict() for warning in converted.warnings]
        label_names = [AI_GENERATED_LABEL]
        if mark_agent_friendly:
            label_names.append(AGENT_FRIENDLY_LABEL)
        try:
            await self._add_labels(_string_or_none(created.get("id")) or "", label_names)
        except AtlassianServiceError as exc:
            warnings.append(
                {
                    "type": "label_write_failed",
                    "message": exc.message,
                    "source_excerpt": ",".join(label_names),
                }
            )
        return {
            "id": _string_or_none(created.get("id")),
            "parent_id": parent_ref["id"],
            "parent_type": parent_ref["type"],
            "space_id": parent_ref["space_id"],
            "status": _string_or_none(created.get("status")),
            "title": _string_or_none(created.get("title")) or normalized_title,
            "version_number": _version_number(created),
            "web_url": _web_url(created),
            "labels": label_names,
            "conversion_warnings": [warning.to_dict() for warning in converted.warnings],
            "warnings": warnings,
            "errors": [],
        }

    async def update_page(
        self,
        *,
        page_url: str,
        body_markdown: str,
        title: str | None = None,
        version_message: str | None = None,
    ) -> dict[str, Any]:
        page_id = resolve_page_id(page_id=None, page_url=page_url)
        current = await self._get_page(page_id)
        current_title = _string_or_none(current.get("title"))
        next_title = title.strip() if title is not None else current_title
        if not next_title:
            raise AtlassianServiceError(
                type="invalid_request",
                message="Updated page title must not be empty.",
                segment="input",
                retryable=False,
            )
        current_version = _version_number(current)
        if current_version is None:
            raise AtlassianServiceError(
                type="invalid_response",
                message="Current page response did not include version.number.",
                segment="page",
                source_api="GET /wiki/api/v2/pages/{id}",
                retryable=False,
            )
        converted = markdown_to_storage(body_markdown)
        storage_value = with_ai_generated_notice(converted.value)
        body: dict[str, Any] = {
            "id": page_id,
            "status": "current",
            "title": next_title,
            "body": {"representation": "storage", "value": storage_value},
            "version": {"number": current_version + 1},
        }
        if version_message:
            body["version"]["message"] = version_message
        result = await self._client.put_json(
            f"/wiki/api/v2/pages/{page_id}",
            body=body,
            source_api="PUT /wiki/api/v2/pages/{id}",
        )
        updated = result.body if isinstance(result.body, dict) else {}
        warnings = [warning.to_dict() for warning in converted.warnings]
        try:
            await self._add_labels(page_id, [AI_GENERATED_LABEL])
        except AtlassianServiceError as exc:
            warnings.append(
                {
                    "type": "label_write_failed",
                    "message": exc.message,
                    "source_excerpt": AI_GENERATED_LABEL,
                }
            )
        return {
            "id": _string_or_none(updated.get("id")) or page_id,
            "parent_id": _string_or_none(updated.get("parentId")) or _string_or_none(current.get("parentId")),
            "parent_type": _string_or_none(updated.get("parentType")) or _string_or_none(current.get("parentType")),
            "space_id": _string_or_none(updated.get("spaceId")) or _string_or_none(current.get("spaceId")),
            "status": _string_or_none(updated.get("status")),
            "title": _string_or_none(updated.get("title")) or next_title,
            "version_number": _version_number(updated),
            "web_url": _web_url(updated, base_url=self._base_url) or _web_url(current, base_url=self._base_url),
            "labels": [AI_GENERATED_LABEL],
            "conversion_warnings": [warning.to_dict() for warning in converted.warnings],
            "warnings": warnings,
            "errors": [],
        }

    async def _resolve_parent(
        self,
        *,
        parent_url: str,
    ) -> dict[str, str]:
        resolved_parent_id = resolve_parent_id(parent_url=parent_url)
        page_error: AtlassianServiceError | None = None
        try:
            page = await self._get_page(resolved_parent_id)
            return _parent_ref_from_response(page, parent_type="page")
        except AtlassianServiceError as exc:
            page_error = exc
        try:
            result = await self._client.get_json(
                f"/wiki/api/v2/folders/{resolved_parent_id}",
                source_api="GET /wiki/api/v2/folders/{id}",
            )
        except AtlassianServiceError as folder_error:
            raise AtlassianServiceError(
                type="not_found",
                message=(
                    "Parent id could not be resolved as a Confluence page or folder. "
                    f"Page lookup failed: {page_error.message if page_error else 'unknown'}. "
                    f"Folder lookup failed: {folder_error.message}."
                ),
                segment="parent",
                retryable=False,
            ) from folder_error
        if not isinstance(result.body, dict):
            raise AtlassianServiceError(
                type="invalid_response",
                message="Confluence folder response was not a JSON object.",
                segment="parent",
                source_api=result.source_api,
                retryable=False,
            )
        return _parent_ref_from_response(result.body, parent_type="folder")

    async def _get_page(self, page_id: str) -> dict[str, Any]:
        result = await self._client.get_json(
            f"/wiki/api/v2/pages/{page_id}",
            params={"body-format": "storage"},
            source_api="GET /wiki/api/v2/pages/{id}",
        )
        if not isinstance(result.body, dict):
            raise AtlassianServiceError(
                type="invalid_response",
                message="Confluence page response was not a JSON object.",
                segment="page",
                source_api=result.source_api,
                retryable=False,
            )
        return result.body

    async def _normalize_page(
        self,
        page: dict[str, Any],
        *,
        include_footer_comments: bool,
    ) -> dict[str, Any]:
        warnings: list[dict[str, Any]] = []
        user_cache: dict[str, dict[str, str | None]] = {}
        owner = await self._enrich_user(_string_or_none(page.get("ownerId")), user_cache, warnings)
        author = await self._enrich_user(_string_or_none(page.get("authorId")), user_cache, warnings)
        page_id = _string_or_none(page.get("id"))
        comments: list[dict[str, Any]] = []
        if include_footer_comments and page_id:
            comments = await self._footer_comments(page_id, user_cache, warnings)
        return {
            "id": page_id,
            "parent_id": _string_or_none(page.get("parentId")),
            "space_id": _string_or_none(page.get("spaceId")),
            "status": _string_or_none(page.get("status")),
            "title": _string_or_none(page.get("title")),
            "created_at": _string_or_none(page.get("createdAt")),
            "owner": owner,
            "author": author,
            "version_number": _version_number(page),
            "body": _storage_body(page),
            "footer_comments": comments,
            "web_url": _web_url(page),
            "warnings": warnings,
        }

    async def _enrich_user(
        self,
        account_id: str | None,
        cache: dict[str, dict[str, str | None]],
        warnings: list[dict[str, Any]],
    ) -> dict[str, str | None]:
        if not account_id:
            return {"account_id": None, "display_name": None}
        if account_id in cache:
            return cache[account_id]
        value = {"account_id": account_id, "display_name": None}
        try:
            result = await self._client.get_json(
                "/wiki/rest/api/user",
                params={"accountId": account_id},
                source_api="GET /wiki/rest/api/user",
            )
            if isinstance(result.body, dict):
                value["display_name"] = _string_or_none(result.body.get("displayName"))
        except AtlassianServiceError as exc:
            warnings.append(
                {
                    "type": "user_enrich_failed",
                    "message": exc.message,
                    "source_excerpt": account_id,
                }
            )
        cache[account_id] = value
        return value

    async def _footer_comments(
        self,
        page_id: str,
        user_cache: dict[str, dict[str, str | None]],
        warnings: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        try:
            result = await self._client.get_json(
                f"/wiki/api/v2/pages/{page_id}/footer-comments",
                params={"body-format": "storage"},
                source_api="GET /wiki/api/v2/pages/{id}/footer-comments",
            )
        except AtlassianServiceError as exc:
            warnings.append(
                {
                    "type": "footer_comments_failed",
                    "message": exc.message,
                    "source_excerpt": page_id,
                }
            )
            return []
        comments = _as_list(result.body.get("results") if isinstance(result.body, dict) else None)
        output: list[dict[str, Any]] = []
        for comment in comments:
            if not isinstance(comment, dict):
                continue
            author = await self._enrich_user(
                _comment_author_id(comment),
                user_cache,
                warnings,
            )
            output.append(
                {
                    "id": _string_or_none(comment.get("id")),
                    "author": author,
                    "created_at": _string_or_none(comment.get("createdAt")),
                    "updated_at": _string_or_none(comment.get("updatedAt")),
                    "body": _storage_body(comment),
                }
            )
        return output

    async def _matching_parent_search_item(
        self,
        *,
        parent_id: str,
        terms: list[str],
        search_field: str,
        match: str,
        warnings: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        try:
            parent = await self._get_page(parent_id)
        except AtlassianServiceError as exc:
            warnings.append(
                {
                    "type": "parent_page_read_failed",
                    "message": exc.message,
                    "source_excerpt": parent_id,
                }
            )
            return None
        if not _page_matches(parent, terms=terms, search_field=search_field, match=match):
            return None
        return _page_to_search_item(parent)

    async def _add_labels(self, page_id: str, labels: list[str]) -> None:
        if not page_id:
            raise AtlassianServiceError(
                type="invalid_response",
                message="Created page response did not include id, so labels could not be added.",
                segment="labels",
                retryable=False,
            )
        body = [{"prefix": "global", "name": label} for label in labels]
        await self._client.post_json(
            f"/wiki/rest/api/content/{page_id}/label",
            body=body,
            source_api="POST /wiki/rest/api/content/{id}/label",
        )


def resolve_page_id(*, page_id: str | None, page_url: str | None) -> str:
    if bool(page_id) == bool(page_url):
        raise AtlassianServiceError(
            type="invalid_request",
            message="Exactly one of page_id or page_url must be provided.",
            segment="input",
            retryable=False,
        )
    if page_id:
        return _normalize_page_id(page_id, field_name="page_id")
    parsed = urlparse(page_url or "")
    query_page_id = parse_qs(parsed.query).get("pageId", [None])[0]
    if query_page_id:
        return _normalize_page_id(query_page_id, field_name="page_url")
    match = re.search(r"/pages/(\d+)(?:/|$)", parsed.path)
    if match:
        return match.group(1)
    raise AtlassianServiceError(
        type="invalid_request",
        message="page_url did not include a Confluence page id.",
        segment="input",
        retryable=False,
    )


def resolve_parent_id(*, parent_url: str | None) -> str:
    if not parent_url:
        raise AtlassianServiceError(
            type="invalid_request",
            message="parent_url must be provided.",
            segment="input",
            retryable=False,
        )
    parsed = urlparse(parent_url or "")
    query_page_id = parse_qs(parsed.query).get("pageId", [None])[0]
    if query_page_id:
        return _normalize_page_id(query_page_id, field_name="parent_url")
    match = re.search(r"/(?:pages|folder)/(\d+)(?:/|$)", parsed.path)
    if match:
        return match.group(1)
    raise AtlassianServiceError(
        type="invalid_request",
        message="parent_url did not include a Confluence page or folder id.",
        segment="input",
        retryable=False,
    )


def _parent_ref_from_response(value: dict[str, Any], *, parent_type: str) -> dict[str, str]:
    parent_id = _string_or_none(value.get("id"))
    space_id = _string_or_none(value.get("spaceId"))
    if not parent_id or not space_id:
        raise AtlassianServiceError(
            type="invalid_response",
            message=f"Parent {parent_type} response did not include id and spaceId.",
            segment="parent",
            retryable=False,
        )
    return {"id": parent_id, "type": parent_type, "space_id": space_id}


def _build_search_cql(
    *,
    terms: list[str],
    search_field: str,
    parent_id: str | None,
    agent_friendly_only: bool,
    match: str,
) -> str:
    clauses = ['type = "page"']
    if parent_id:
        clauses.append(f"ancestor = {parent_id}")
    if agent_friendly_only:
        clauses.append(f'label = "{AGENT_FRIENDLY_LABEL}"')
    if terms:
        text_clauses = [f'{search_field} ~ "{_escape_cql_string(term)}"' for term in terms]
        joiner = " AND " if match == "all" else " OR "
        clause = joiner.join(text_clauses)
        clauses.append(f"({clause})" if len(text_clauses) > 1 else clause)
    return " AND ".join(clauses) + " ORDER BY lastmodified DESC"


def _normalize_text(text: str | Iterable[str] | None) -> list[str]:
    if text is None:
        return []
    if isinstance(text, str):
        return [value for value in [text.strip()] if value]
    return [str(value).strip() for value in text if str(value).strip()]


def _normalize_search_field(search_field: str) -> str:
    normalized = search_field.strip().lower()
    if normalized not in {"text", "title"}:
        raise AtlassianServiceError(
            type="invalid_request",
            message="search_field must be one of: text, title.",
            segment="input",
            retryable=False,
        )
    return normalized


def _normalize_match(match: str) -> str:
    normalized = match.strip().lower()
    if normalized not in {"all", "any"}:
        raise AtlassianServiceError(
            type="invalid_request",
            message="match must be one of: all, any.",
            segment="input",
            retryable=False,
        )
    return normalized


def _bounded_max_results(value: int) -> int:
    if value <= 0:
        raise AtlassianServiceError(
            type="invalid_request",
            message="max_results must be greater than 0.",
            segment="input",
            retryable=False,
        )
    return min(value, 50)


def _normalize_page_id(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized or not normalized.isdecimal():
        raise AtlassianServiceError(
            type="invalid_request",
            message=f"{field_name} must be a numeric Confluence page id.",
            segment="input",
            retryable=False,
        )
    return normalized


def _normalize_search_result(item: Any, *, base_url: str | None = None) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {}
    content = item.get("content") if isinstance(item.get("content"), dict) else item
    return {
        "id": _string_or_none(content.get("id")),
        "title": _string_or_none(content.get("title")) or _string_or_none(item.get("title")),
        "type": _string_or_none(content.get("type")),
        "space_id": _space_id(content),
        "web_url": _web_url(content, base_url=base_url) or _web_url(item, base_url=base_url),
        "excerpt": _string_or_none(item.get("excerpt")),
        "last_modified": _string_or_none(item.get("lastModified")),
    }


def _page_to_search_item(page: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _string_or_none(page.get("id")),
        "title": _string_or_none(page.get("title")),
        "type": "page",
        "space_id": _string_or_none(page.get("spaceId")),
        "web_url": _web_url(page),
        "excerpt": None,
        "last_modified": None,
    }


def _page_matches(page: dict[str, Any], *, terms: list[str], search_field: str, match: str) -> bool:
    if not terms:
        return True
    haystack = _string_or_none(page.get("title")) or ""
    if search_field == "text":
        haystack = f"{haystack} {_storage_body(page).get('value') or ''}"
    lowered = haystack.lower()
    checks = [term.lower() in lowered for term in terms]
    return all(checks) if match == "all" else any(checks)


def _dedupe_search_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for item in items:
        item_id = _string_or_none(item.get("id"))
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)
        output.append(item)
    return output


def _storage_body(value: dict[str, Any]) -> dict[str, str | None]:
    body = value.get("body") if isinstance(value.get("body"), dict) else {}
    storage = body.get("storage") if isinstance(body.get("storage"), dict) else {}
    return {
        "representation": _string_or_none(storage.get("representation")) or "storage",
        "value": _string_or_none(storage.get("value")),
    }


def _version_number(value: dict[str, Any]) -> int | None:
    version = value.get("version") if isinstance(value.get("version"), dict) else {}
    number = version.get("number")
    return number if isinstance(number, int) else None


def _web_url(value: dict[str, Any], *, base_url: str | None = None) -> str | None:
    links = value.get("_links") if isinstance(value.get("_links"), dict) else {}
    webui = _string_or_none(links.get("webui"))
    base = _string_or_none(links.get("base"))
    if webui and webui.startswith("http"):
        return webui
    if webui and base:
        return f"{base.rstrip('/')}/{webui.lstrip('/')}"
    if webui and base_url:
        path = webui if webui.startswith("/wiki/") else f"/wiki/{webui.lstrip('/')}"
        return f"{base_url.rstrip('/')}{path}"
    return webui


def _space_id(value: dict[str, Any]) -> str | None:
    if _string_or_none(value.get("spaceId")):
        return _string_or_none(value.get("spaceId"))
    space = value.get("space") if isinstance(value.get("space"), dict) else {}
    return _string_or_none(space.get("id"))


def _comment_author_id(comment: dict[str, Any]) -> str | None:
    for key in ("authorId", "creatorId"):
        if _string_or_none(comment.get(key)):
            return _string_or_none(comment.get(key))
    author = comment.get("author") if isinstance(comment.get("author"), dict) else {}
    return _string_or_none(author.get("accountId"))


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _escape_cql_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
