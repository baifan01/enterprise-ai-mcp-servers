from __future__ import annotations

import datetime as dt
import unittest

from mcp_datawarehouse.heartbeat_gap import analyze_heartbeat_gaps
from mcp_datawarehouse.models import OCPPEvent


def event(timestamp: dt.datetime, event_type: str) -> OCPPEvent:
    return OCPPEvent(
        sso_id="suby1100012048",
        operation_timestamp=timestamp,
        ocpp_message_type=event_type,
    )


class HeartbeatGapAnalyzerTest(unittest.TestCase):
    def test_detects_legacy_gap_without_intermediate_ocpp_event(self) -> None:
        start = dt.datetime(2026, 1, 1, 0, 0, 0)
        periods = analyze_heartbeat_gaps(
            [
                event(dt.datetime(2025, 12, 1, 14, 20, 0), "Heartbeat"),
                event(dt.datetime(2026, 1, 5, 0, 0, 0), "Heartbeat"),
            ],
            analysis_start=start,
            analysis_end=dt.datetime(2026, 1, 10, 0, 0, 0),
            offline_threshold_seconds=1800,
        )

        self.assertEqual(len(periods), 1)
        self.assertEqual(periods[0].offline_start, start)
        self.assertEqual(periods[0].offline_restore, dt.datetime(2026, 1, 5, 0, 0, 0))
        self.assertTrue(periods[0].evidence["clipped_to_requested_window"])

    def test_intermediate_ocpp_event_suppresses_gap(self) -> None:
        periods = analyze_heartbeat_gaps(
            [
                event(dt.datetime(2026, 1, 1, 10, 0, 0), "Heartbeat"),
                event(dt.datetime(2026, 1, 1, 10, 20, 0), "StatusNotification"),
                event(dt.datetime(2026, 1, 1, 12, 0, 0), "Heartbeat"),
            ],
            analysis_start=dt.datetime(2026, 1, 1, 10, 0, 0),
            analysis_end=dt.datetime(2026, 1, 1, 12, 0, 0),
            offline_threshold_seconds=1800,
        )

        self.assertEqual(periods, [])

    def test_clips_gap_that_crosses_window_end(self) -> None:
        periods = analyze_heartbeat_gaps(
            [
                event(dt.datetime(2026, 1, 1, 10, 30, 0), "Heartbeat"),
                event(dt.datetime(2026, 1, 1, 12, 0, 0), "Heartbeat"),
            ],
            analysis_start=dt.datetime(2026, 1, 1, 10, 0, 0),
            analysis_end=dt.datetime(2026, 1, 1, 11, 0, 0),
            offline_threshold_seconds=1800,
        )

        self.assertEqual(len(periods), 1)
        self.assertEqual(periods[0].offline_start, dt.datetime(2026, 1, 1, 10, 30, 0))
        self.assertEqual(periods[0].offline_restore, dt.datetime(2026, 1, 1, 11, 0, 0))


if __name__ == "__main__":
    unittest.main()
