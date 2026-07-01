from __future__ import annotations

import unittest

from mcp_driivz.settings import DriivzSettings


class DriivzSettingsTest(unittest.TestCase):
    def test_runtime_environment_credentials_validate(self) -> None:
        settings = DriivzSettings(
            username="env-user",
            password="env-password",
            timeout_seconds=42,
        )

        settings.validate_auth()
        self.assertEqual(settings.username, "env-user")
        self.assertEqual(settings.password.get_secret_value(), "env-password")
        self.assertEqual(settings.timeout_seconds, 42)

    def test_missing_credentials_mentions_runtime_environment(self) -> None:
        settings = DriivzSettings(_env_file=None)

        with self.assertRaises(ValueError) as context:
            settings.validate_auth()

        self.assertIn("runtime environment", str(context.exception))
        self.assertNotIn("personal-secrets.env", str(context.exception))


if __name__ == "__main__":
    unittest.main()
