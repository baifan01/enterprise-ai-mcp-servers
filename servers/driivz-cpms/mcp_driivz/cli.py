"""Command line entrypoint for developing the Driivz core service."""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from mcp_driivz.service import review_site_runtime_by_key


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Driivz CPMS core service CLI.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    review_key = subparsers.add_parser(
        "review-site-runtime-by-key",
        help="Review site/runtime context by company device ID or EVSE ID.",
    )
    review_key.add_argument("key", help="Company device ID / Driivz EVSE ID.")
    review_key.add_argument(
        "--key-type",
        choices=("auto", "device_id", "evse_id"),
        default="auto",
        help="How to interpret the key. Auto treats values containing '*' as EVSE IDs.",
    )
    review_key.add_argument(
        "--no-recent-sessions",
        action="store_true",
        help="Skip the recent EV transaction lookup.",
    )
    review_key.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")

    return parser


async def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "review-site-runtime-by-key":
        return await review_site_runtime_by_key(
            args.key,
            key_type=args.key_type,
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
