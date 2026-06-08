from __future__ import annotations

import unittest

from mcp_datawarehouse.service import query_device_online_status, query_ocpp_sequence


class ServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_input_fails_without_databricks_auth(self) -> None:
        result = await query_ocpp_sequence(
            sso_id="",
            time_from="2026-06-03T19:00:00Z",
            time_to="2026-06-03T20:00:00Z",
            user_id="fan.bai@ubitricity.com",
        )

        self.assertEqual(result["event_count"], 0)
        self.assertEqual(result["errors"][0]["type"], "invalid_request")
        self.assertEqual(result["errors"][0]["segment"], "input")

    async def test_ocpp_heartbeat_window_limit_fails_without_databricks_auth(self) -> None:
        result = await query_ocpp_sequence(
            sso_id="suby1100012048",
            time_from="2026-06-01T00:00:00Z",
            time_to="2026-06-03T00:00:01Z",
            user_id="fan.bai@ubitricity.com",
            include_heartbeats=True,
        )

        self.assertEqual(result["event_count"], 0)
        self.assertEqual(result["errors"][0]["type"], "invalid_request")
        self.assertIn("48 hours", result["errors"][0]["message"])

    async def test_ocpp_without_heartbeat_window_limit_fails_without_databricks_auth(self) -> None:
        result = await query_ocpp_sequence(
            sso_id="suby1100012048",
            time_from="2026-05-01T00:00:00Z",
            time_to="2026-06-01T00:00:01Z",
            user_id="fan.bai@ubitricity.com",
        )

        self.assertEqual(result["event_count"], 0)
        self.assertEqual(result["errors"][0]["type"], "invalid_request")
        self.assertIn("31 days", result["errors"][0]["message"])

    async def test_online_status_invalid_input_fails_without_databricks_auth(self) -> None:
        result = await query_device_online_status(
            sso_id="",
            time_from="2026-06-03T19:00:00Z",
            time_to="2026-06-03T20:00:00Z",
            user_id="fan.bai@ubitricity.com",
        )

        self.assertFalse(result["has_offline"])
        self.assertEqual(result["offline_periods"], [])
        self.assertEqual(result["errors"][0]["type"], "invalid_request")
        self.assertEqual(result["errors"][0]["segment"], "input")

    async def test_online_status_window_limit_fails_without_databricks_auth(self) -> None:
        result = await query_device_online_status(
            sso_id="suby1100012048",
            time_from="2026-05-01T00:00:00Z",
            time_to="2026-06-01T00:00:01Z",
            user_id="fan.bai@ubitricity.com",
        )

        self.assertFalse(result["has_offline"])
        self.assertEqual(result["offline_periods"], [])
        self.assertEqual(result["errors"][0]["type"], "invalid_request")
        self.assertIn("31 days", result["errors"][0]["message"])

    async def test_online_status_requires_user_id_before_databricks_auth(self) -> None:
        result = await query_device_online_status(
            sso_id="suby1100012048",
            time_from="2026-06-03T19:00:00Z",
            time_to="2026-06-03T20:00:00Z",
        )

        self.assertFalse(result["has_offline"])
        self.assertEqual(result["errors"][0]["type"], "invalid_request")
        self.assertIn("user_id is required", result["errors"][0]["message"])


if __name__ == "__main__":
    unittest.main()
