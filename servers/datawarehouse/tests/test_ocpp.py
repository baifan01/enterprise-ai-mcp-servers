from __future__ import annotations

import datetime as dt
import unittest
from typing import Any

from mcp_datawarehouse.models import QueryResult
from mcp_datawarehouse.ocpp import OCPPSequenceQuery
from mcp_datawarehouse.settings import DatawarehouseSettings


class FakeClient:
    def __init__(self, result: QueryResult) -> None:
        self.settings = DatawarehouseSettings(
            databricks_server_hostname="host",
            databricks_http_path="/sql",
            databricks_token="token",
        )
        self.result = result
        self.calls: list[tuple[str, list[Any] | None, str]] = []

    async def execute(
        self,
        query: str,
        parameters: list[Any] | None = None,
        *,
        source_query: str,
    ) -> QueryResult:
        self.calls.append((query, parameters, source_query))
        return self.result


class OCPPSequenceQueryTest(unittest.IsolatedAsyncioTestCase):
    async def test_query_compacts_status_and_authorization_events(self) -> None:
        start = dt.datetime(2026, 6, 3, 19, 0, 0)
        client = FakeClient(
            QueryResult(
                columns=[
                    "sso_id",
                    "operation_timestamp",
                    "ocpp_message_type",
                    "ocpp_request_body",
                    "ocpp_response_body",
                ],
                rows=[
                    (
                        "suby1100012048",
                        start,
                        "StatusNotification",
                        '{"connectorId":1,"status":"Preparing","errorCode":"NoError"}',
                        "{}",
                    ),
                    (
                        "suby1100012048",
                        start + dt.timedelta(seconds=3),
                        "StartTransaction",
                        '{"connectorId":1,"idTag":"abc","meterStart":123}',
                        '{"transactionId":456,"idTagInfo":{"status":"Accepted"}}',
                    ),
                ],
            )
        )

        result = await OCPPSequenceQuery(client).query(
            sso_id="suby1100012048",
            time_from=start,
            time_to=start + dt.timedelta(minutes=1),
        )

        self.assertEqual(result["event_count"], 2)
        self.assertEqual(result["event_type_counts"]["StatusNotification"], 1)
        self.assertEqual(result["events"][0]["status"], "Preparing")
        self.assertEqual(result["events"][0]["error_code"], "NoError")
        self.assertEqual(result["events"][1]["response_summary"]["idTagInfo"]["status"], "Accepted")
        self.assertNotIn("request", result["events"][1])

    async def test_query_can_include_bounded_raw_payload(self) -> None:
        start = dt.datetime(2026, 6, 3, 19, 0, 0)
        body = '{"connectorId":1,"status":"' + ("A" * 150) + '"}'
        client = FakeClient(
            QueryResult(
                columns=[
                    "sso_id",
                    "operation_timestamp",
                    "ocpp_message_type",
                    "ocpp_request_body",
                    "ocpp_response_body",
                ],
                rows=[("suby1100012048", start, "StatusNotification", body, None)],
            )
        )

        result = await OCPPSequenceQuery(client).query(
            sso_id="suby1100012048",
            time_from=start,
            time_to=start + dt.timedelta(minutes=1),
            include_raw_payload=True,
            max_payload_chars=100,
        )

        self.assertTrue(result["events"][0]["request"]["truncated"])
        self.assertEqual(len(result["events"][0]["request"]["text"]), 100)

    async def test_query_with_heartbeats_is_limited_to_48_hours(self) -> None:
        start = dt.datetime(2026, 6, 1, 0, 0, 0)
        client = FakeClient(
            QueryResult(
                columns=[
                    "sso_id",
                    "operation_timestamp",
                    "ocpp_message_type",
                    "ocpp_request_body",
                    "ocpp_response_body",
                ],
                rows=[],
            )
        )

        result = await OCPPSequenceQuery(client).query(
            sso_id="suby1100012048",
            time_from=start,
            time_to=start + dt.timedelta(hours=48),
            include_heartbeats=True,
        )

        self.assertEqual(result["event_count"], 0)
        self.assertEqual(len(client.calls), 1)

        with self.assertRaisesRegex(ValueError, "heartbeats is limited to 48 hours"):
            await OCPPSequenceQuery(client).query(
                sso_id="suby1100012048",
                time_from=start,
                time_to=start + dt.timedelta(hours=48, seconds=1),
                include_heartbeats=True,
            )

    async def test_query_without_heartbeats_is_limited_to_31_days(self) -> None:
        start = dt.datetime(2026, 6, 1, 0, 0, 0)
        client = FakeClient(
            QueryResult(
                columns=[
                    "sso_id",
                    "operation_timestamp",
                    "ocpp_message_type",
                    "ocpp_request_body",
                    "ocpp_response_body",
                ],
                rows=[],
            )
        )

        result = await OCPPSequenceQuery(client).query(
            sso_id="suby1100012048",
            time_from=start,
            time_to=start + dt.timedelta(days=31),
        )

        self.assertEqual(result["event_count"], 0)
        self.assertEqual(len(client.calls), 1)

        with self.assertRaisesRegex(ValueError, "without heartbeats is limited to 31 days"):
            await OCPPSequenceQuery(client).query(
                sso_id="suby1100012048",
                time_from=start,
                time_to=start + dt.timedelta(days=31, seconds=1),
            )


if __name__ == "__main__":
    unittest.main()
