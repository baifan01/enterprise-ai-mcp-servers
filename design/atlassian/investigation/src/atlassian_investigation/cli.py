"""CLI entrypoint for Atlassian Jira ticket investigation."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .client import AtlassianClient, AtlassianClientError
from .tickets import TicketQueryService
from .wiki import WikiSearchService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Atlassian investigation CLI.")
    parser.add_argument(
        "--env-file",
        default=None,
        help="Optional .env path. Defaults to design/atlassian/investigation/.env.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    read = subparsers.add_parser("read-ticket", help="Read one Jira ticket by issue key.")
    read.add_argument("issue_key", help="Issue key, for example CTI-15.")
    read.add_argument("--fields", default="", help="Comma-separated Jira fields.")
    read.add_argument("--expand", default="", help="Comma-separated Jira expand values.")
    read.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")

    search = subparsers.add_parser("search-tickets", help="Search Jira tickets by structured filters.")
    search.add_argument("keywords", nargs="*", help="Optional keywords to search in Jira text.")
    search.add_argument(
        "--text-field",
        choices=["text", "summary", "description"],
        default="text",
        help="Jira text field used for keyword search.",
    )
    search.add_argument(
        "--project",
        action="append",
        default=[],
        help="Optional Jira project key. Can be repeated.",
    )
    search.add_argument(
        "--creator",
        action="append",
        default=[],
        help="Optional Jira creator account/email value. Can be repeated.",
    )
    search.add_argument(
        "--assignee",
        action="append",
        default=[],
        help="Optional Jira assignee account/email value. Can be repeated.",
    )
    search.add_argument(
        "--status",
        action="append",
        default=[],
        help="Optional Jira status name. Can be repeated.",
    )
    search.add_argument(
        "--issue-type",
        action="append",
        default=[],
        help="Optional Jira issue type name. Can be repeated.",
    )
    search.add_argument(
        "--match",
        choices=["all", "any"],
        default="all",
        help="Whether all keywords or any keyword must match.",
    )
    search.add_argument("--max-results", type=int, default=20, help="Maximum results, capped at 100.")
    search.add_argument("--fields", default="", help="Comma-separated Jira fields.")
    search.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")

    wiki = subparsers.add_parser("search-wiki", help="Search Confluence wiki content.")
    wiki.add_argument("keywords", nargs="*", help="Optional keywords to search in Confluence.")
    wiki.add_argument(
        "--search-field",
        choices=["text", "title"],
        default="text",
        help="Confluence CQL field used for keyword search.",
    )
    wiki.add_argument(
        "--space",
        action="append",
        default=[],
        help="Optional Confluence space key. Can be repeated.",
    )
    wiki.add_argument(
        "--type",
        action="append",
        default=[],
        choices=["page", "blogpost", "comment", "attachment"],
        help="Optional Confluence content type. Defaults to page. Can be repeated.",
    )
    wiki.add_argument(
        "--match",
        choices=["all", "any"],
        default="all",
        help="Whether all keywords or any keyword must match.",
    )
    wiki.add_argument("--max-results", type=int, default=10, help="Maximum results, capped at 50.")
    wiki.add_argument("--expand", default="", help="Comma-separated Confluence expand values.")
    wiki.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    return parser


def run(args: argparse.Namespace) -> dict[str, Any]:
    client = AtlassianClient.from_env(env_file=args.env_file)
    if args.command == "read-ticket":
        return TicketQueryService(client).get_ticket(
            args.issue_key,
            fields=_split_csv(args.fields),
            expand=_split_csv(args.expand),
        )
    if args.command == "search-tickets":
        return TicketQueryService(client).search_tickets(
            text=args.keywords,
            text_field=args.text_field,
            project_keys=args.project,
            creators=args.creator,
            assignees=args.assignee,
            statuses=args.status,
            issue_types=args.issue_type,
            match=args.match,
            max_results=args.max_results,
            fields=_split_csv(args.fields),
        )
    if args.command == "search-wiki":
        return WikiSearchService(client).search_wiki(
            text=args.keywords,
            search_field=args.search_field,
            space_keys=args.space,
            content_types=args.type or None,
            match=args.match,
            max_results=args.max_results,
            expand=_split_csv(args.expand),
        )
    raise ValueError(f"Unsupported command: {args.command}")


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = run(args)
    except (AtlassianClientError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    indent = 2 if getattr(args, "pretty", False) else None
    print(json.dumps(result, ensure_ascii=False, indent=indent, default=str))
    return 0


def _split_csv(raw_value: str) -> list[str] | None:
    values = [item.strip() for item in raw_value.split(",") if item.strip()]
    return values or None


if __name__ == "__main__":
    raise SystemExit(main())
