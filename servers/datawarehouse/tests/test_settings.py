from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp_datawarehouse.settings import DatawarehouseSettings


class DatawarehouseSettingsTest(unittest.TestCase):
    def test_runtime_environment_credentials_take_priority(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = DatawarehouseSettings(
                agent_root=Path(tmp),
                user_id="fan.bai@ubitricity.com",
                databricks_server_hostname="env-host",
                databricks_http_path="/env",
                databricks_token="env-token",
            )

        self.assertEqual(settings.databricks_server_hostname, "env-host")
        self.assertEqual(settings.databricks_http_path, "/env")
        self.assertEqual(settings.databricks_token.get_secret_value(), "env-token")

    def test_user_personal_secrets_fill_missing_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            secrets_dir = Path(tmp) / "users" / "fan.bai@ubitricity.com" / "secrets"
            secrets_dir.mkdir(parents=True)
            (secrets_dir / "personal-secrets.env").write_text(
                "\n".join(
                    [
                        "DATABRICKS_SERVER_HOSTNAME=personal-host",
                        "DATABRICKS_HTTP_PATH=/personal",
                        "DATABRICKS_TOKEN=personal-token",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict("os.environ", {}, clear=True):
                settings = DatawarehouseSettings(
                    agent_root=Path(tmp),
                    user_id="fan.bai@ubitricity.com",
                    databricks_catalog="catalog",
                    databricks_schema="schema",
                )

        self.assertEqual(settings.databricks_server_hostname, "personal-host")
        self.assertEqual(settings.databricks_http_path, "/personal")
        self.assertEqual(settings.databricks_token.get_secret_value(), "personal-token")
        self.assertEqual(settings.databricks_catalog, "catalog")
        self.assertEqual(settings.databricks_schema, "schema")

    def test_missing_personal_secret_is_reported_by_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = DatawarehouseSettings(agent_root=Path(tmp), user_id="fan.bai@ubitricity.com")

        with self.assertRaises(ValueError) as context:
            settings.validate_databricks_auth()

        self.assertIn("Personal secrets lookup failed", str(context.exception))


if __name__ == "__main__":
    unittest.main()
