from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mcp_atlassian.settings import AtlassianSettings


class AtlassianSettingsTest(unittest.TestCase):
    def test_runtime_environment_credentials_take_priority(self) -> None:
        settings = AtlassianSettings(
            base_url="https://runtime.atlassian.net",
            email="runtime@example.com",
            api_token="runtime-token",
            user_id="fan.bai@example.com",
        )

        settings.validate_auth()
        self.assertEqual(settings.base_url, "https://runtime.atlassian.net")
        self.assertEqual(settings.email, "runtime@example.com")
        self.assertEqual(settings.api_token.get_secret_value(), "runtime-token")

    def test_user_personal_secrets_fill_missing_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            secret_dir = Path(tmp) / "users" / "fan.bai@example.com" / "secrets"
            secret_dir.mkdir(parents=True)
            (secret_dir / "personal-secrets.env").write_text(
                "\n".join(
                    [
                        "ATLASSIAN_BASE_URL=https://secret.atlassian.net",
                        "ATLASSIAN_EMAIL=secret@example.com",
                        "ATLASSIAN_API_TOKEN=secret-token",
                    ]
                ),
                encoding="utf-8",
            )

            settings = AtlassianSettings(agent_root=tmp, user_id="fan.bai@example.com")

        settings.validate_auth()
        self.assertEqual(settings.base_url, "https://secret.atlassian.net")
        self.assertEqual(settings.email, "secret@example.com")
        self.assertEqual(settings.api_token.get_secret_value(), "secret-token")

    def test_missing_personal_secret_is_reported_by_validation(self) -> None:
        settings = AtlassianSettings(agent_root="/tmp/does-not-exist", user_id="fan.bai@example.com")

        with self.assertRaisesRegex(ValueError, "Personal secrets lookup failed"):
            settings.validate_auth()


if __name__ == "__main__":
    unittest.main()
