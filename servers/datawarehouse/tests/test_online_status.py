from __future__ import annotations

import datetime as dt
import unittest
from typing import Any

from mcp_datawarehouse.models import QueryResult
from mcp_datawarehouse.online_status import DeviceOnlineStatusQuery
from mcp_datawarehouse.settings import DatawarehouseSettings


class FakeClient:
    def __init__(self, results: list[QueryResult]) -> None:
        self.settings = DatawarehouseSettings(
            databricks_server_hostname="host",
            databricks_http_path="/sql",
            databricks_token="token",
        )
        self.results = list(results)
        self.calls: list[tuple[str, list[Any] | None, str]] = []

    async def execute(
        self,
        query: str,
        parameters: list[Any] | None = None,
        *,
        source_query: str,
    ) -> QueryResult:
        self.calls.append((query, parameters, source_query))
        return self.results.pop(0)


def ocpp_result(rows: list[tuple[str, dt.datetime, str]]) -> QueryResult:
    return QueryResult(
        columns=["sso_id", "operation_timestamp", "ocpp_message_type", "ocpp_request_body"],
        rows=[(*row, None) for row in rows],
    )


class DeviceOnlineStatusQueryTest(unittest.IsolatedAsyncioTestCase):
    async def test_queries_only_window_and_detects_observed_offline_period(self) -> None:
        client = FakeClient(
            [
                ocpp_result(
                    [
                        ("suby1100012048", dt.datetime(2026, 1, 2, 7, 0, 0), "Heartbeat"),
                        ("suby1100012048", dt.datetime(2026, 1, 2, 8, 0, 0), "Heartbeat"),
                    ]
                ),
            ]
        )

        result = await DeviceOnlineStatusQuery(client).query(
            sso_id=" suby1100012048 ",
            time_from=dt.datetime(2026, 1, 1, 0, 0, 0),
            time_to=dt.datetime(2026, 1, 10, 0, 0, 0),
            now=dt.datetime(2026, 1, 11, 0, 0, 0),
        )

        self.assertEqual(len(client.calls), 1)
        for query, _parameters, _source_query in client.calls:
            self.assertIn("WHERE sso_id = ?", query)
            self.assertNotIn("REGEXP_EXTRACT", query)
        _window_query, window_parameters, _window_source = client.calls[0]
        self.assertEqual(window_parameters[1], dt.datetime(2026, 1, 1, 0, 0, 0))
        self.assertEqual(window_parameters[2], dt.datetime(2026, 1, 10, 0, 0, 0))
        self.assertEqual(
            [source_query for _query, _parameters, source_query in client.calls],
            ["charger_ocpp_operations_v.online_status.window_events"],
        )
        self.assertNotIn("boundary_policy", result["query"])
        self.assertNotIn("queried_previous_event_before_window", result["query"])
        self.assertNotIn("queried_next_event_after_window", result["query"])
        self.assertTrue(result["has_offline"])
        self.assertEqual(result["offline_periods"][0]["offline_start"], "2026-01-02T07:00:00")
        self.assertEqual(result["offline_periods"][0]["offline_restore"], "2026-01-02T08:00:00")
        self.assertEqual(result["coverage"]["observed_time_from"], "2026-01-02T07:00:00")
        self.assertEqual(result["coverage"]["observed_time_to"], "2026-01-02T08:00:00")
        self.assertNotIn("latest_event_before_or_at_end", result)
        self.assertNotIn("previous_event_before_window", result)
        self.assertNotIn("next_event_after_window", result)
        self.assertEqual(result["event_count_in_window"], 2)
        self.assertEqual(result["heartbeat_count_in_window"], 2)

    async def test_empty_window_reports_no_observed_coverage(self) -> None:
        client = FakeClient(
            [
                ocpp_result([]),
            ]
        )

        result = await DeviceOnlineStatusQuery(client).query(
            sso_id="suby1100012048",
            time_from=dt.datetime(2026, 1, 1, 10, 0, 0),
            time_to=dt.datetime(2026, 1, 1, 10, 25, 0),
            recent_end_grace_seconds=1800,
            now=dt.datetime(2026, 1, 1, 10, 30, 0),
        )

        self.assertEqual(len(client.calls), 1)
        self.assertEqual(result["coverage"]["requested_time_from"], "2026-01-01T10:00:00")
        self.assertEqual(result["coverage"]["requested_time_to"], "2026-01-01T10:25:00")
        self.assertIsNone(result["coverage"]["observed_time_from"])
        self.assertIsNone(result["coverage"]["observed_time_to"])
        self.assertIsNone(result["coverage"]["first_event_in_window"])
        self.assertIsNone(result["coverage"]["last_event_in_window"])
        self.assertNotIn("queried_next_event_after_window", result["query"])
        self.assertFalse(result["has_offline"])

    async def test_online_status_window_is_limited_to_31_days(self) -> None:
        start = dt.datetime(2026, 1, 1, 0, 0, 0)
        client = FakeClient([ocpp_result([])])

        result = await DeviceOnlineStatusQuery(client).query(
            sso_id="suby1100012048",
            time_from=start,
            time_to=start + dt.timedelta(days=31),
        )

        self.assertFalse(result["has_offline"])
        self.assertEqual(len(client.calls), 1)

        with self.assertRaisesRegex(ValueError, "online status query is limited to 31 days"):
            await DeviceOnlineStatusQuery(client).query(
                sso_id="suby1100012048",
                time_from=start,
                time_to=start + dt.timedelta(days=31, seconds=1),
            )


if __name__ == "__main__":
    unittest.main()
