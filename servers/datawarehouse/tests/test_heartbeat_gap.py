from __future__ import annotations

import datetime as dt
import unittest

from mcp_datawarehouse.heartbeat_gap import analyze_heartbeat_gaps
from mcp_datawarehouse.models import OCPPEvent


def event(timestamp: dt.datetime, event_type: str, request_body: str | None = None) -> OCPPEvent:
    return OCPPEvent(
        sso_id="suby1100012048",
        operation_timestamp=timestamp,
        ocpp_message_type=event_type,
        ocpp_request_body=request_body,
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

    def test_charging_status_suppresses_following_gap(self) -> None:
        periods = analyze_heartbeat_gaps(
            [
                event(dt.datetime(2026, 1, 1, 10, 0, 0), "Heartbeat"),
                event(
                    dt.datetime(2026, 1, 1, 10, 20, 0),
                    "StatusNotification",
                    '[2,"id","StatusNotification",{"status":"Charging"}]',
                ),
                event(dt.datetime(2026, 1, 1, 12, 0, 0), "Heartbeat"),
            ],
            analysis_start=dt.datetime(2026, 1, 1, 10, 0, 0),
            analysis_end=dt.datetime(2026, 1, 1, 12, 0, 0),
            offline_threshold_seconds=1800,
        )

        self.assertEqual(periods, [])

    def test_non_charging_intermediate_ocpp_event_can_start_gap(self) -> None:
        periods = analyze_heartbeat_gaps(
            [
                event(dt.datetime(2026, 1, 1, 10, 0, 0), "Heartbeat"),
                event(
                    dt.datetime(2026, 1, 1, 10, 20, 0),
                    "StatusNotification",
                    '{"status":"Available"}',
                ),
                event(dt.datetime(2026, 1, 1, 12, 0, 0), "Heartbeat"),
            ],
            analysis_start=dt.datetime(2026, 1, 1, 10, 0, 0),
            analysis_end=dt.datetime(2026, 1, 1, 12, 0, 0),
            offline_threshold_seconds=1800,
        )

        self.assertEqual(len(periods), 1)
        self.assertEqual(periods[0].offline_start, dt.datetime(2026, 1, 1, 10, 20, 0))
        self.assertEqual(periods[0].evidence["previous_event_type"], "StatusNotification")

    def test_start_transaction_suppresses_following_gap(self) -> None:
        periods = analyze_heartbeat_gaps(
            [
                event(dt.datetime(2026, 1, 1, 10, 0, 0), "StartTransaction"),
                event(dt.datetime(2026, 1, 1, 12, 0, 0), "Heartbeat"),
            ],
            analysis_start=dt.datetime(2026, 1, 1, 10, 0, 0),
            analysis_end=dt.datetime(2026, 1, 1, 12, 0, 0),
            offline_threshold_seconds=1800,
        )

        self.assertEqual(periods, [])

    def test_detects_gap_when_restore_event_is_status_notification(self) -> None:
        periods = analyze_heartbeat_gaps(
            [
                event(dt.datetime(2026, 6, 8, 0, 30, 0), "Heartbeat"),
                event(dt.datetime(2026, 6, 8, 1, 45, 0), "StatusNotification"),
            ],
            analysis_start=dt.datetime(2026, 6, 8, 0, 0, 0),
            analysis_end=dt.datetime(2026, 6, 8, 8, 0, 0),
            offline_threshold_seconds=1800,
        )

        self.assertEqual(len(periods), 1)
        self.assertEqual(periods[0].offline_start, dt.datetime(2026, 6, 8, 0, 30, 0))
        self.assertEqual(periods[0].offline_restore, dt.datetime(2026, 6, 8, 1, 45, 0))
        self.assertEqual(periods[0].evidence["restore_event_type"], "StatusNotification")

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
