from __future__ import annotations

import unittest

from mcp_driivz.cli import build_parser


class DriivzCliTest(unittest.TestCase):
    def test_review_site_runtime_by_key_accepts_evse_id(self) -> None:
        args = build_parser().parse_args(
            [
                "review-site-runtime-by-key",
                "DE*UBI*E10043108",
                "--key-type",
                "evse_id",
                "--user-id",
                "fan.bai@ubitricity.com",
            ]
        )

        self.assertEqual(args.command, "review-site-runtime-by-key")
        self.assertEqual(args.key, "DE*UBI*E10043108")
        self.assertEqual(args.key_type, "evse_id")
        self.assertEqual(args.user_id, "fan.bai@ubitricity.com")

if __name__ == "__main__":
    unittest.main()
