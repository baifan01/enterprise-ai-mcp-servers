from __future__ import annotations

import contextlib
import io
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
            ]
        )

        self.assertEqual(args.command, "review-site-runtime-by-key")
        self.assertEqual(args.key, "DE*UBI*E10043108")
        self.assertEqual(args.key_type, "evse_id")
        self.assertFalse(hasattr(args, "user_id"))

    def test_review_site_runtime_by_key_does_not_accept_user_id(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            build_parser().parse_args(
                [
                    "review-site-runtime-by-key",
                    "DE*UBI*E10043108",
                    "--user-id",
                    "fan.bai@ubitricity.com",
                ]
            )


if __name__ == "__main__":
    unittest.main()
