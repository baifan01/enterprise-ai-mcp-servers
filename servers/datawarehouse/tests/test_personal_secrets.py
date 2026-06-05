from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ubi_mcp_common import PersonalSecretsError, load_personal_secret_values, personal_secrets_path


class PersonalSecretsTest(unittest.TestCase):
    def test_resolves_user_personal_secrets_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = personal_secrets_path(Path(tmp), "fan.bai@ubitricity.com")

        self.assertEqual(
            path.name,
            "personal-secrets.env",
        )
        self.assertIn("fan.bai@ubitricity.com", path.parts)

    def test_rejects_path_traversal_user_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(PersonalSecretsError):
                personal_secrets_path(Path(tmp), "../other-user")

    def test_loads_only_required_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            secrets_dir = Path(tmp) / "users" / "fan.bai@ubitricity.com" / "secrets"
            secrets_dir.mkdir(parents=True)
            (secrets_dir / "personal-secrets.env").write_text(
                "\n".join(
                    [
                        "DATABRICKS_SERVER_HOSTNAME=host",
                        "DATABRICKS_HTTP_PATH='/sql/path'",
                        "DATABRICKS_TOKEN=token",
                        "OTHER_SECRET=unused",
                    ]
                ),
                encoding="utf-8",
            )

            values = load_personal_secret_values(
                agent_root=Path(tmp),
                user_id="fan.bai@ubitricity.com",
                required_keys=["DATABRICKS_SERVER_HOSTNAME", "DATABRICKS_HTTP_PATH"],
            )

        self.assertEqual(
            values,
            {
                "DATABRICKS_SERVER_HOSTNAME": "host",
                "DATABRICKS_HTTP_PATH": "/sql/path",
            },
        )

    def test_missing_required_key_fails_without_secret_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            secrets_dir = Path(tmp) / "users" / "fan.bai@ubitricity.com" / "secrets"
            secrets_dir.mkdir(parents=True)
            (secrets_dir / "personal-secrets.env").write_text(
                "DATABRICKS_SERVER_HOSTNAME=host\n",
                encoding="utf-8",
            )

            with self.assertRaises(PersonalSecretsError) as context:
                load_personal_secret_values(
                    agent_root=Path(tmp),
                    user_id="fan.bai@ubitricity.com",
                    required_keys=["DATABRICKS_SERVER_HOSTNAME", "DATABRICKS_TOKEN"],
                )

        self.assertIn("DATABRICKS_TOKEN", str(context.exception))


if __name__ == "__main__":
    unittest.main()
