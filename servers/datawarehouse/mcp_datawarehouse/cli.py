"""Command line entrypoint for developing data warehouse core queries."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from typing import Any

from mcp_datawarehouse.service import query_charging_attempts, query_ocpp_sequence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Data warehouse core service CLI.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    attempts = subparsers.add_parser(
        "query-charging-attempts",
        help="Query charging attempts by SSO ID or EVSE ID and time range.",
    )
    attempts.add_argument("--sso-id", help="Internal device SSO ID.")
    attempts.add_argument("--evse-id", help="External EVSE ID, resolved to SSO ID.")
    attempts.add_argument("--time-from", required=True, help="Inclusive start timestamp.")
    attempts.add_argument("--time-to", required=True, help="Inclusive end timestamp.")
    attempts.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")

    ocpp = subparsers.add_parser(
        "query-ocpp-sequence",
        help="Query compact OCPP event sequence by SSO ID and time range.",
    )
    ocpp.add_argument("--sso-id", required=True, help="Internal device SSO ID.")
    ocpp.add_argument("--time-from", required=True, help="Inclusive start timestamp.")
    ocpp.add_argument("--time-to", required=True, help="Inclusive end timestamp.")
    ocpp.add_argument(
        "--include-heartbeats",
        action="store_true",
        help="Include Heartbeat events in the OCPP sequence.",
    )
    ocpp.add_argument(
        "--include-raw-payload",
        action="store_true",
        help="Include bounded raw request/response payload snippets.",
    )
    ocpp.add_argument(
        "--max-payload-chars",
        type=int,
        default=1200,
        help="Maximum raw payload characters per request or response.",
    )
    ocpp.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    return parser


async def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "query-charging-attempts":
        return await query_charging_attempts(
            sso_id=args.sso_id,
            evse_id=args.evse_id,
            time_from=args.time_from,
            time_to=args.time_to,
        )
    if args.command == "query-ocpp-sequence":
        return await query_ocpp_sequence(
            sso_id=args.sso_id,
            time_from=args.time_from,
            time_to=args.time_to,
            include_heartbeats=args.include_heartbeats,
            include_raw_payload=args.include_raw_payload,
            max_payload_chars=args.max_payload_chars,
        )
    raise ValueError(f"Unsupported command: {args.command}")


def main() -> None:
    logging.basicConfig(level=logging.ERROR)
    args = build_parser().parse_args()
    result = asyncio.run(run(args))
    indent = 2 if args.pretty else None
    print(json.dumps(result, ensure_ascii=False, indent=indent, default=str))


if __name__ == "__main__":
    main()
