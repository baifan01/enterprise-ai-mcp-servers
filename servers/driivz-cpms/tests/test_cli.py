from __future__ import annotations

import unittest

from mcp_driivz.cli import build_parser


class DriivzCliTest(unittest.TestCase):
    def test_review_site_runtime_by_device_accepts_user_id(self) -> None:
        args = build_parser().parse_args(
            [
                "review-site-runtime-by-device",
                "suby1100008277",
                "--user-id",
                "fan.bai@ubitricity.com",
            ]
        )

        self.assertEqual(args.command, "review-site-runtime-by-device")
        self.assertEqual(args.device_id, "suby1100008277")
        self.assertEqual(args.user_id, "fan.bai@ubitricity.com")


if __name__ == "__main__":
    unittest.main()
