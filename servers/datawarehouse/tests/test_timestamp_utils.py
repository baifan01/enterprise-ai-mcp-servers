from __future__ import annotations

import unittest

from mcp_datawarehouse.timestamp_utils import coerce_datetime


class TimestampUtilsTest(unittest.TestCase):
    def test_coerce_datetime_drops_timezone_for_databricks_queries(self) -> None:
        parsed = coerce_datetime("2026-06-03T19:00:04.531Z")

        self.assertEqual(parsed.isoformat(), "2026-06-03T19:00:04.531000")


if __name__ == "__main__":
    unittest.main()
