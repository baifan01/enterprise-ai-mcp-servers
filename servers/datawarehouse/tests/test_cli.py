from __future__ import annotations

import contextlib
import io
import unittest

from mcp_datawarehouse.cli import build_parser


class DatawarehouseCliTest(unittest.TestCase):
    def test_charging_attempts_accepts_user_id(self) -> None:
        args = build_parser().parse_args(
            [
                "query-charging-attempts",
                "--sso-id",
                "suby1100012048",
                "--time-from",
                "2026-06-03T19:00:00Z",
                "--time-to",
                "2026-06-03T20:00:00Z",
                "--user-id",
                "fan.bai@ubitricity.com",
            ]
        )

        self.assertEqual(args.user_id, "fan.bai@ubitricity.com")

    def test_ocpp_sequence_accepts_user_id(self) -> None:
        args = build_parser().parse_args(
            [
                "query-ocpp-sequence",
                "--sso-id",
                "suby1100012048",
                "--time-from",
                "2026-06-03T19:00:00Z",
                "--time-to",
                "2026-06-03T20:00:00Z",
                "--user-id",
                "fan.bai@ubitricity.com",
            ]
        )

        self.assertEqual(args.user_id, "fan.bai@ubitricity.com")

    def test_online_status_accepts_user_id(self) -> None:
        args = build_parser().parse_args(
            [
                "query-device-online-status",
                "--sso-id",
                "suby1100012048",
                "--time-from",
                "2026-06-03T19:00:00Z",
                "--time-to",
                "2026-06-03T20:00:00Z",
                "--user-id",
                "fan.bai@ubitricity.com",
            ]
        )

        self.assertEqual(args.user_id, "fan.bai@ubitricity.com")

    def test_online_status_requires_user_id(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            build_parser().parse_args(
                [
                    "query-device-online-status",
                    "--sso-id",
                    "suby1100012048",
                    "--time-from",
                    "2026-06-03T19:00:00Z",
                    "--time-to",
                    "2026-06-03T20:00:00Z",
                ]
            )


if __name__ == "__main__":
    unittest.main()
