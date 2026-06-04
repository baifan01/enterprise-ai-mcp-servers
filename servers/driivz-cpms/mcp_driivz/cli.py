"""Command line entrypoint for developing the Driivz core service."""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from mcp_driivz.service import review_site_runtime_by_device


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Driivz CPMS core service CLI.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    review = subparsers.add_parser(
        "review-site-runtime",
        help="Review site/runtime context by company device ID.",
    )
    review.add_argument("device_id", help="Company device ID / Driivz identityKey.")
    review.add_argument(
        "--no-recent-sessions",
        action="store_true",
        help="Skip the recent EV transaction lookup.",
    )
    review.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    return parser


async def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "review-site-runtime":
        return await review_site_runtime_by_device(
            args.device_id,
            include_recent_sessions=not args.no_recent_sessions,
        )
    raise ValueError(f"Unsupported command: {args.command}")


def main() -> None:
    args = build_parser().parse_args()
    result = asyncio.run(run(args))
    indent = 2 if args.pretty else None
    print(json.dumps(result, ensure_ascii=False, indent=indent, default=str))


if __name__ == "__main__":
    main()
