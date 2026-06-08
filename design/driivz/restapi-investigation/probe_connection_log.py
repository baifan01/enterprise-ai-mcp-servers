"""Probe Driivz charger WebSocket connection logs by charger identity key.

This script is for REST investigation only. It is not production MCP code.
It reuses the local investigation client/settings from probe_device.py and
does not print secrets such as password, cookie, or dmsTicket.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from probe_device import DriivzClient, InvestigationSettings


async def probe_connection_log(args: argparse.Namespace) -> None:
    settings = InvestigationSettings()
    settings.validate_auth()

    async with DriivzClient(settings) as client:
        profile = await client.post_json(
            "/v1/chargers/profiles/filter",
            params={"pageSize": 20, "pageNumber": 0},
            body={"identityKey": args.device_id},
        )

        profile_items = profile.data if isinstance(profile.data, list) else []
        charger_profiles = [item for item in profile_items if isinstance(item, dict)]
        charger_ids = [
            item.get("id")
            for item in charger_profiles
            if isinstance(item.get("id"), int)
        ]

        result: dict[str, Any] = {
            "device_id": args.device_id,
            "profile": {
                "status_code": profile.status_code,
                "request_id": profile.request_id,
                "count": profile.count,
                "charger_ids": charger_ids,
                "profiles": [
                    {
                        "id": item.get("id"),
                        "identityKey": item.get("identityKey"),
                        "caption": item.get("caption"),
                        "siteId": item.get("siteId"),
                        "status": item.get("status"),
                        "provisionStatus": item.get("provisionStatus"),
                        "serialNumber": item.get("serialNumber"),
                    }
                    for item in charger_profiles
                ],
            },
        }

        if args.profile_only or not charger_ids:
            print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
            return

        charger_id = charger_ids[0]
        connection_log = await client.post_json(
            "/v1/chargers/connection-log/filter",
            params={
                "pageSize": args.page_size,
                "pageNumber": args.page_number,
                "sortBy": args.sort_by,
            },
            body={
                "chargerId": charger_id,
                "startDate": args.date_from,
                "endDate": args.date_to,
            },
        )
        result["connection_log"] = {
            "source_api": "POST /v1/chargers/connection-log/filter",
            "request_body": {
                "chargerId": charger_id,
                "startDate": args.date_from,
                "endDate": args.date_to,
            },
            "query": {
                "pageSize": args.page_size,
                "pageNumber": args.page_number,
                "sortBy": args.sort_by,
            },
            "status_code": connection_log.status_code,
            "request_id": connection_log.request_id,
            "count": connection_log.count,
            "data": connection_log.data,
        }

        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Probe charger WebSocket connection logs by Driivz identity key."
    )
    parser.add_argument("device_id", help="Company deviceID / Driivz charger identity key")
    parser.add_argument(
        "--from",
        dest="date_from",
        default="2026-06-08T00:00:00Z",
        help="Connection log window start, ISO 8601 UTC.",
    )
    parser.add_argument(
        "--to",
        dest="date_to",
        default="2026-06-08T08:00:00Z",
        help="Connection log window end, ISO 8601 UTC.",
    )
    parser.add_argument("--page-size", type=int, default=20)
    parser.add_argument("--page-number", type=int, default=0)
    parser.add_argument("--sort-by", default="date:asc")
    parser.add_argument(
        "--profile-only",
        action="store_true",
        help="Only resolve the charger profile and charger id.",
    )
    return parser


if __name__ == "__main__":
    asyncio.run(probe_connection_log(build_parser().parse_args()))
