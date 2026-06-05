from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp_driivz.settings import DriivzSettings


class DriivzSettingsTest(unittest.TestCase):
    def test_runtime_environment_credentials_take_priority(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = DriivzSettings(
                agent_root=Path(tmp),
                user_id="fan.bai@ubitricity.com",
                username="env-user",
                password="env-password",
            )

        self.assertEqual(settings.username, "env-user")
        self.assertEqual(settings.password.get_secret_value(), "env-password")

    def test_user_personal_secrets_fill_missing_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            secrets_dir = Path(tmp) / "users" / "fan.bai@ubitricity.com" / "secrets"
            secrets_dir.mkdir(parents=True)
            (secrets_dir / "personal-secrets.env").write_text(
                "\n".join(
                    [
                        "DRIIVZ_USERNAME=personal-user",
                        "DRIIVZ_PASSWORD=personal-password",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict("os.environ", {}, clear=True):
                settings = DriivzSettings(
                    agent_root=Path(tmp),
                    user_id="fan.bai@ubitricity.com",
                    timeout_seconds=42,
                )

        self.assertEqual(settings.username, "personal-user")
        self.assertEqual(settings.password.get_secret_value(), "personal-password")
        self.assertEqual(settings.timeout_seconds, 42)

    def test_missing_personal_secret_is_reported_by_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = DriivzSettings(agent_root=Path(tmp), user_id="fan.bai@ubitricity.com")

        with self.assertRaises(ValueError) as context:
            settings.validate_auth()

        self.assertIn("Personal secrets lookup failed", str(context.exception))


if __name__ == "__main__":
    unittest.main()
