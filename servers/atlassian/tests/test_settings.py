from __future__ import annotations

import unittest

from mcp_atlassian.settings import AtlassianSettings


class AtlassianSettingsTest(unittest.TestCase):
    def test_runtime_environment_credentials_validate(self) -> None:
        settings = AtlassianSettings(
            base_url="https://runtime.atlassian.net",
            email="runtime@example.com",
            api_token="runtime-token",
        )

        settings.validate_auth()
        self.assertEqual(settings.base_url, "https://runtime.atlassian.net")
        self.assertEqual(settings.email, "runtime@example.com")
        self.assertEqual(settings.api_token.get_secret_value(), "runtime-token")

    def test_missing_credentials_mentions_runtime_environment(self) -> None:
        settings = AtlassianSettings(_env_file=None)

        with self.assertRaisesRegex(ValueError, "runtime environment") as context:
            settings.validate_auth()

        self.assertNotIn("personal-secrets.env", str(context.exception))


if __name__ == "__main__":
    unittest.main()
