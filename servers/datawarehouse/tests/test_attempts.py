from __future__ import annotations

import datetime as dt
import unittest
from typing import Any

from mcp_datawarehouse.attempts import ChargingAttemptsQuery
from mcp_datawarehouse.models import QueryResult
from mcp_datawarehouse.settings import DatawarehouseSettings


class FakeClient:
    def __init__(self, results: dict[str, QueryResult]) -> None:
        self.settings = DatawarehouseSettings(
            databricks_server_hostname="host",
            databricks_http_path="/sql",
            databricks_token="token",
        )
        self.results = results
        self.calls: list[tuple[str, list[Any] | None, str]] = []

    async def execute(
        self,
        query: str,
        parameters: list[Any] | None = None,
        *,
        source_query: str,
    ) -> QueryResult:
        self.calls.append((query, parameters, source_query))
        return self.results[source_query]


class ChargingAttemptsQueryTest(unittest.IsolatedAsyncioTestCase):
    async def test_query_merges_adjacent_attempt_rows(self) -> None:
        base = dt.datetime(2026, 6, 3, 19, 0, 0)
        client = FakeClient(
            {
                "kpi_charging_attempts_enriched_v": QueryResult(
                    columns=[
                        "sso_id",
                        "connector_id",
                        "charging_attempt_start",
                        "charging_attempt_end",
                        "session_consumption_kwh",
                        "transaction_id",
                        "transaction_id_tag",
                        "transaction_stop_reason",
                        "authorization_status",
                        "session_status",
                        "session_charging_duration_seconds",
                        "seconds_in_preparing",
                        "seconds_in_charging",
                        "remote_start_status",
                        "invalid_session_reasons_from_source",
                        "has_connector_lock_failure",
                        "attempt_with_alfen_error_304_timeout",
                    ],
                    rows=[
                        (
                            "suby1100012048",
                            "1",
                            base,
                            base + dt.timedelta(minutes=1),
                            0.1,
                            "tx-1",
                            "tag",
                            "Local",
                            "Accepted",
                            "COMPLETED",
                            60,
                            4,
                            55,
                            "Accepted",
                            None,
                            False,
                            False,
                        ),
                        (
                            "suby1100012048",
                            "1",
                            base + dt.timedelta(seconds=45),
                            base + dt.timedelta(minutes=2),
                            0.2,
                            "tx-2",
                            "tag",
                            "Local",
                            "Accepted",
                            "COMPLETED",
                            75,
                            5,
                            70,
                            "Accepted",
                            None,
                            False,
                            False,
                        ),
                    ],
                )
            }
        )

        result = await ChargingAttemptsQuery(client).query(
            sso_id="suby1100012048",
            time_from=base,
            time_to=base + dt.timedelta(minutes=3),
        )

        self.assertEqual(result["raw_attempt_count"], 2)
        self.assertEqual(result["merged_attempt_count"], 1)
        self.assertTrue(result["had_adjacent_merge"])
        self.assertEqual(result["merged_attempts"][0]["attempt_count"], 2)
        self.assertAlmostEqual(result["merged_attempts"][0]["total_consumption_kwh"], 0.3)

    async def test_query_resolves_evse_id_to_sso_id(self) -> None:
        start = dt.datetime(2026, 6, 3, 19, 0, 0)
        client = FakeClient(
            {
                "charger_location_charger_v": QueryResult(
                    columns=["sso_id"],
                    rows=[("suby1100012048",)],
                ),
                "kpi_charging_attempts_enriched_v": QueryResult(columns=[], rows=[]),
            }
        )

        result = await ChargingAttemptsQuery(client).query(
            evse_id="GB*UBI*E10050732",
            time_from=start,
            time_to=start + dt.timedelta(minutes=10),
        )

        self.assertEqual(result["query"]["sso_id"], "suby1100012048")
        self.assertEqual(result["raw_attempt_count"], 0)
        self.assertEqual(client.calls[0][2], "charger_location_charger_v")


if __name__ == "__main__":
    unittest.main()
