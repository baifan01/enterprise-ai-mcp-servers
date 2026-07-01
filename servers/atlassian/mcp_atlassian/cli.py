"""Command line entrypoint for Atlassian local-tool service methods."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from typing import Any

from mcp_atlassian.service import (
    create_wiki_child_page,
    read_wiki_page,
    search_wiki_pages,
    update_wiki_page,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Atlassian core service CLI.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    read = subparsers.add_parser("read-wiki-page", help="Read one Confluence wiki page.")
    read_id = read.add_mutually_exclusive_group(required=True)
    read_id.add_argument("--page-id", help="Numeric Confluence page id.")
    read_id.add_argument("--page-url", help="Confluence browser URL.")
    read.add_argument(
        "--include-footer-comments",
        action="store_true",
        help="Read root footer comments.",
    )
    read.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")

    search = subparsers.add_parser("search-wiki-pages", help="Search Confluence wiki pages.")
    search.add_argument("text", nargs="*", help="Keyword text. Multiple values are matched by --match.")
    search.add_argument("--search-field", default="text", choices=["text", "title"])
    search.add_argument("--parent-url", help="Confluence parent page browser URL.")
    search.add_argument("--agent-friendly-only", action="store_true")
    search.add_argument("--match", default="all", choices=["all", "any"])
    search.add_argument("--max-results", type=int, default=10)
    search.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")

    create = subparsers.add_parser(
        "create-wiki-child-page",
        help="Create a Confluence child page from supported Markdown.",
    )
    create.add_argument("--parent-url", required=True, help="Confluence parent page or folder browser URL.")
    create.add_argument("--title", required=True, help="New page title.")
    create.add_argument("--body-markdown", required=True, help="Markdown body content.")
    create.add_argument("--mark-agent-friendly", action="store_true")
    create.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")

    update = subparsers.add_parser(
        "update-wiki-page",
        help="Replace an existing Confluence page body from supported Markdown.",
    )
    update.add_argument("--page-url", required=True, help="Confluence page browser URL.")
    update.add_argument("--body-markdown", required=True, help="Markdown body content.")
    update.add_argument("--title", help="Optional replacement page title.")
    update.add_argument("--version-message", help="Optional Confluence version message.")
    update.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")

    return parser


async def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "read-wiki-page":
        return await read_wiki_page(
            page_id=args.page_id,
            page_url=args.page_url,
            include_footer_comments=args.include_footer_comments,
        )
    if args.command == "search-wiki-pages":
        return await search_wiki_pages(
            text=args.text,
            search_field=args.search_field,
            parent_url=args.parent_url,
            agent_friendly_only=args.agent_friendly_only,
            match=args.match,
            max_results=args.max_results,
        )
    if args.command == "create-wiki-child-page":
        return await create_wiki_child_page(
            parent_url=args.parent_url,
            title=args.title,
            body_markdown=args.body_markdown,
            mark_agent_friendly=args.mark_agent_friendly,
        )
    if args.command == "update-wiki-page":
        return await update_wiki_page(
            page_url=args.page_url,
            body_markdown=args.body_markdown,
            title=args.title,
            version_message=args.version_message,
        )
    raise ValueError(f"Unsupported command: {args.command}")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    args = build_parser().parse_args()
    result = asyncio.run(run(args))
    indent = 2 if args.pretty else None
    print(json.dumps(result, ensure_ascii=False, indent=indent, default=str))


if __name__ == "__main__":
    main()
