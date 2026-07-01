"""Business-level Atlassian service functions.

These async facades are the stable local-tool entrypoints for Codex testing and
future wrapper generation. They coordinate settings, client lifetime, Confluence
adapters, logging, and safe failure conversion. HTTP details stay in client.py
and Confluence page details stay in wiki.py.
"""

from __future__ import annotations

import logging
from typing import Any, Iterable

from mcp_atlassian.client import AtlassianClient
from mcp_atlassian.errors import AtlassianServiceError
from mcp_atlassian.settings import AtlassianSettings
from mcp_atlassian.wiki import WikiService

logger = logging.getLogger(__name__)


async def read_wiki_page(
    *,
    page_id: str | None = None,
    page_url: str | None = None,
    include_footer_comments: bool = False,
) -> dict[str, Any]:
    """Read a Confluence wiki page by id or browser URL.

    Tool:
        name: read-wiki-page
        wrapper: atlassian-read
        mode: read
        summary: Read one Confluence page and return normalized page content.

    When to use:
        Use when the user provides a Confluence page id or URL and the agent
        needs the full page body, page metadata, and optionally root footer
        comments.

    Parameters:
        page_id:
            Optional numeric Confluence page id. Exactly one of page_id or
            page_url must be provided.
        page_url:
            Optional browser URL copied from Confluence. Exactly one of page_id
            or page_url must be provided.
        include_footer_comments:
            If true, also read root footer comments. Defaults to false.

    Examples:
        atlassian-read.sh read-wiki-page --page-id 5781061778
        atlassian-read.sh read-wiki-page --page-url "https://example.atlassian.net/wiki/spaces/UM/pages/5781061778/Page"
        atlassian-read.sh read-wiki-page --page-id 5781061778 --include-footer-comments

    Output:
        JSON with normalized page id, parent_id, space_id, title, owner, author,
        version_number, storage body, optional footer_comments, web_url, warnings,
        and errors.

    Safety:
        Read-only. Uses fixed body-format=storage internally and does not expose
        arbitrary Confluence API parameters.
    """

    logger.info(
        "Starting Atlassian service request: kind=read_wiki_page page_id=%s "
        "has_page_url=%s include_footer_comments=%s",
        page_id,
        bool(page_url),
        include_footer_comments,
    )
    query = {
        "page_id": page_id,
        "page_url": page_url,
        "include_footer_comments": include_footer_comments,
    }
    try:
        async with AtlassianClient(AtlassianSettings()) as client:
            result = await WikiService(client).read_page(
                page_id=page_id,
                page_url=page_url,
                include_footer_comments=include_footer_comments,
            )
    except AtlassianServiceError as exc:
        return _failed_result(query=query, errors=[exc], kind="read_wiki_page")
    except ValueError as exc:
        return _failed_result(
            query=query,
            errors=[_invalid_request(str(exc))],
            kind="read_wiki_page",
        )
    result["errors"] = []
    logger.info(
        "Completed Atlassian service request: kind=read_wiki_page page_id=%s", result.get("id")
    )
    return result


async def search_wiki_pages(
    *,
    text: str | Iterable[str] | None = None,
    search_field: str = "text",
    parent_url: str | None = None,
    agent_friendly_only: bool = False,
    match: str = "all",
    max_results: int = 10,
) -> dict[str, Any]:
    """Search Confluence wiki pages with structured parameters.

    Tool:
        name: search-wiki-pages
        wrapper: atlassian-read
        mode: read
        summary: Search Confluence pages by title or body text.

    When to use:
        Use when the user wants to find wiki pages by keywords, optionally under
        a parent page. Use this before read-wiki-page when the page id or URL is
        not known.

    Parameters:
        text:
            Optional keywords. Supports one string or multiple terms.
        search_field:
            One of: text, title. Defaults to text.
        parent_url:
            Optional Confluence browser URL. Limits search to the parent page
            and all descendants.
        agent_friendly_only:
            If true, only search pages labeled ubitricity-agent-friendly.
        match:
            One of: all, any. Defaults to all.
        max_results:
            Maximum number of results. Capped at 50.

    Examples:
        atlassian-read.sh search-wiki-pages "design system" --search-field title
        atlassian-read.sh search-wiki-pages "runbook" --agent-friendly-only
        atlassian-read.sh search-wiki-pages "release" --parent-url "https://example.atlassian.net/wiki/spaces/UM/pages/123456789/Page"

    Output:
        JSON with query metadata, result_count, page summaries, warnings, and
        errors.

    Safety:
        Read-only. Does not expose arbitrary CQL. The service builds CQL from
        structured parameters and always limits content type to page.
    """

    logger.info(
        "Starting Atlassian service request: kind=search_wiki_pages search_field=%s "
        "has_parent_url=%s agent_friendly_only=%s match=%s "
        "max_results=%s",
        search_field,
        bool(parent_url),
        agent_friendly_only,
        match,
        max_results,
    )
    query = {
        "text": text,
        "search_field": search_field,
        "parent_url": parent_url,
        "agent_friendly_only": agent_friendly_only,
        "match": match,
        "max_results": max_results,
    }
    try:
        async with AtlassianClient(AtlassianSettings()) as client:
            result = await WikiService(client).search_pages(
                text=text,
                search_field=search_field,
                parent_url=parent_url,
                agent_friendly_only=agent_friendly_only,
                match=match,
                max_results=max_results,
            )
    except AtlassianServiceError as exc:
        return _failed_result(query=query, errors=[exc], kind="search_wiki_pages")
    except ValueError as exc:
        return _failed_result(
            query=query,
            errors=[_invalid_request(str(exc))],
            kind="search_wiki_pages",
        )
    logger.info(
        "Completed Atlassian service request: kind=search_wiki_pages result_count=%s",
        result.get("result_count"),
    )
    return result


async def create_wiki_child_page(
    *,
    parent_url: str,
    title: str,
    body_markdown: str,
    mark_agent_friendly: bool = False,
) -> dict[str, Any]:
    """Create a Confluence child page from supported Markdown.

    Tool:
        name: create-wiki-child-page
        wrapper: atlassian-write
        mode: write
        summary: Create a Confluence child page under a required parent page or folder.

    When to use:
        Use when the user explicitly wants to create a new Confluence page under
        a known parent page or folder and provides Markdown body content.

    Parameters:
        parent_url:
            Required Confluence browser URL for a parent page or folder.
        title:
            Required page title.
        body_markdown:
            Required Markdown body using the supported subset.
        mark_agent_friendly:
            If true, also add the ubitricity-agent-friendly label. Defaults to
            false. The ubitricity-ai-generated label is always attempted.

    Examples:
        atlassian-write.sh create-wiki-child-page --parent-url "https://example.atlassian.net/wiki/spaces/UM/folder/123456789" --title "Agent Runbook" --body-markdown "# Runbook" --mark-agent-friendly

    Output:
        JSON with created page id, title, parent_id, parent_type, space_id,
        web_url, labels, conversion_warnings, warnings, and errors.

    Safety:
        Write operation. Creates a Confluence page and attempts to add labels.
        Does not accept arbitrary HTML or storage XHTML; Markdown is converted
        through the bounded internal converter.
    """

    logger.info(
        "Starting Atlassian service request: kind=create_wiki_child_page "
        "has_parent_url=%s title=%s mark_agent_friendly=%s",
        bool(parent_url),
        title,
        mark_agent_friendly,
    )
    query = {
        "parent_url": parent_url,
        "title": title,
        "mark_agent_friendly": mark_agent_friendly,
    }
    try:
        async with AtlassianClient(AtlassianSettings()) as client:
            result = await WikiService(client).create_child_page(
                parent_url=parent_url,
                title=title,
                body_markdown=body_markdown,
                mark_agent_friendly=mark_agent_friendly,
            )
    except AtlassianServiceError as exc:
        return _failed_result(query=query, errors=[exc], kind="create_wiki_child_page")
    except ValueError as exc:
        return _failed_result(
            query=query,
            errors=[_invalid_request(str(exc))],
            kind="create_wiki_child_page",
        )
    logger.info(
        "Completed Atlassian service request: kind=create_wiki_child_page page_id=%s",
        result.get("id"),
    )
    return result


async def update_wiki_page(
    *,
    page_url: str,
    body_markdown: str,
    title: str | None = None,
    version_message: str | None = None,
) -> dict[str, Any]:
    """Update an existing Confluence wiki page from supported Markdown.

    Tool:
        name: update-wiki-page
        wrapper: atlassian-write
        mode: write
        summary: Replace one Confluence page body using a required page URL.

    When to use:
        Use when the user explicitly wants to replace the content of an existing
        Confluence page and provides the page browser URL plus new Markdown body.

    Parameters:
        page_url:
            Required Confluence browser URL for the page to update. Folder URLs
            are not accepted.
        body_markdown:
            Required Markdown body using the supported subset. It replaces the
            previous page body.
        title:
            Optional replacement title. If omitted, the current page title is
            preserved.
        version_message:
            Optional Confluence version message.

    Examples:
        atlassian-write.sh update-wiki-page --page-url "https://example.atlassian.net/wiki/spaces/UM/pages/123456789/Page" --body-markdown "# Updated"
        atlassian-write.sh update-wiki-page --page-url "https://example.atlassian.net/wiki/spaces/UM/pages/123456789/Page" --title "Updated title" --body-markdown "# Updated"

    Output:
        JSON with updated page id, title, parent_id, parent_type, space_id,
        version_number, web_url, labels, conversion_warnings, warnings, and
        errors.

    Safety:
        Write operation. Replaces the target page body and creates a new
        Confluence page version. Does not accept arbitrary HTML or storage XHTML;
        Markdown is converted through the bounded internal converter. The target
        must be a page URL, not a folder URL.
    """

    logger.info(
        "Starting Atlassian service request: kind=update_wiki_page has_page_url=%s "
        "has_title=%s has_version_message=%s",
        bool(page_url),
        title is not None,
        bool(version_message),
    )
    query = {
        "page_url": page_url,
        "title": title,
        "has_version_message": bool(version_message),
    }
    try:
        async with AtlassianClient(AtlassianSettings()) as client:
            result = await WikiService(client).update_page(
                page_url=page_url,
                body_markdown=body_markdown,
                title=title,
                version_message=version_message,
            )
    except AtlassianServiceError as exc:
        return _failed_result(query=query, errors=[exc], kind="update_wiki_page")
    except ValueError as exc:
        return _failed_result(
            query=query,
            errors=[_invalid_request(str(exc))],
            kind="update_wiki_page",
        )
    logger.info(
        "Completed Atlassian service request: kind=update_wiki_page page_id=%s",
        result.get("id"),
    )
    return result


def _failed_result(
    *,
    query: dict[str, Any],
    errors: list[AtlassianServiceError],
    kind: str,
) -> dict[str, Any]:
    log_level = (
        logging.INFO
        if all(error.type == "invalid_request" for error in errors)
        else logging.WARNING
    )
    logger.log(
        log_level,
        "Atlassian service request failed",
        extra={"kind": kind, "error_types": [error.type for error in errors]},
    )
    return {
        "query": _safe_json_value(query),
        "result_count": 0,
        "results": [],
        "warnings": [],
        "errors": [error.to_dict() for error in errors],
    }


def _invalid_request(message: str) -> AtlassianServiceError:
    return AtlassianServiceError(
        type="invalid_request",
        message=message,
        segment="input",
        retryable=False,
    )


def _safe_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _safe_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe_json_value(item) for item in value]
    if isinstance(value, tuple):
        return [_safe_json_value(item) for item in value]
    return value
