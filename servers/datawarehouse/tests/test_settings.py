from __future__ import annotations

import unittest

from mcp_datawarehouse.settings import DatawarehouseSettings


class DatawarehouseSettingsTest(unittest.TestCase):
    def test_runtime_environment_credentials_validate(self) -> None:
        settings = DatawarehouseSettings(
            databricks_server_hostname="env-host",
            databricks_http_path="/env",
            databricks_token="env-token",
            databricks_catalog="catalog",
            databricks_schema="schema",
        )

        settings.validate_databricks_auth()
        self.assertEqual(settings.databricks_server_hostname, "env-host")
        self.assertEqual(settings.databricks_http_path, "/env")
        self.assertEqual(settings.databricks_token.get_secret_value(), "env-token")
        self.assertEqual(settings.databricks_catalog, "catalog")
        self.assertEqual(settings.databricks_schema, "schema")

    def test_missing_credentials_mentions_runtime_environment(self) -> None:
        settings = DatawarehouseSettings(_env_file=None)

        with self.assertRaises(ValueError) as context:
            settings.validate_databricks_auth()

        self.assertIn("runtime environment", str(context.exception))
        self.assertNotIn("personal-secrets.env", str(context.exception))


if __name__ == "__main__":
    unittest.main()
