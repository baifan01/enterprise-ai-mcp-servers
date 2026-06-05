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
        columns=["sso_id", "operation_timestamp", "ocpp_message_type"],
        rows=rows,
    )


class DeviceOnlineStatusQueryTest(unittest.IsolatedAsyncioTestCase):
    async def test_queries_window_edges_and_detects_clipped_offline_period(self) -> None:
        client = FakeClient(
            [
                ocpp_result(
                    [("suby1100012048", dt.datetime(2025, 12, 1, 14, 20, 0), "Heartbeat")]
                ),
                ocpp_result(
                    [("suby1100012048", dt.datetime(2026, 1, 5, 0, 0, 0), "Heartbeat")]
                ),
                ocpp_result([]),
            ]
        )

        result = await DeviceOnlineStatusQuery(client).query(
            sso_id=" suby1100012048 ",
            time_from=dt.datetime(2026, 1, 1, 0, 0, 0),
            time_to=dt.datetime(2026, 1, 10, 0, 0, 0),
            now=dt.datetime(2026, 1, 11, 0, 0, 0),
        )

        self.assertEqual(len(client.calls), 3)
        for query, _parameters, _source_query in client.calls:
            self.assertIn("WHERE sso_id = ?", query)
            self.assertNotIn("REGEXP_EXTRACT", query)
        previous_query, previous_parameters, _previous_source = client.calls[0]
        next_query, next_parameters, _next_source = client.calls[2]
        self.assertIn("AND operation_timestamp >= ?", previous_query)
        self.assertEqual(previous_parameters[1], dt.datetime(2025, 12, 31, 0, 0, 0))
        self.assertIn("AND operation_timestamp <= ?", next_query)
        self.assertEqual(next_parameters[2], dt.datetime(2026, 1, 11, 0, 0, 0))
        self.assertEqual(
            [source_query for _query, _parameters, source_query in client.calls],
            [
                "charger_ocpp_operations_v.online_status.previous_event",
                "charger_ocpp_operations_v.online_status.window_events",
                "charger_ocpp_operations_v.online_status.next_event",
            ],
        )
        self.assertTrue(result["query"]["queried_next_event_after_window"])
        self.assertTrue(result["has_offline"])
        self.assertEqual(result["offline_periods"][0]["offline_start"], "2026-01-01T00:00:00")
        self.assertEqual(result["offline_periods"][0]["offline_restore"], "2026-01-05T00:00:00")
        self.assertEqual(result["event_count_in_window"], 1)
        self.assertEqual(result["heartbeat_count_in_window"], 1)

    async def test_skips_next_event_when_end_is_near_now(self) -> None:
        client = FakeClient(
            [
                ocpp_result(
                    [("suby1100012048", dt.datetime(2026, 1, 1, 10, 0, 0), "Heartbeat")]
                ),
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

        self.assertEqual(len(client.calls), 2)
        self.assertFalse(result["query"]["queried_next_event_after_window"])
        self.assertIsNone(result["next_event_after_window"])


if __name__ == "__main__":
    unittest.main()
