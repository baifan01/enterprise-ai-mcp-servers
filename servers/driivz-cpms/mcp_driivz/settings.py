"""Driivz CPMS server settings."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import AliasChoices, Field, PrivateAttr, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from ubi_mcp_common import PersonalSecretsError, load_personal_secret_values

PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = PROJECT_DIR / ".env"
DEFAULT_BASE_URL = "https://apex-prod.driivz.com:8103/api-gateway"


class DriivzSettings(BaseSettings):
    """Runtime configuration for the Driivz CPMS REST client."""

    model_config = SettingsConfigDict(
        env_prefix="DRIIVZ_",
        env_file=DEFAULT_ENV_FILE,
        extra="ignore",
        populate_by_name=True,
    )

    _credential_source_error: str | None = PrivateAttr(default=None)

    def __init__(self, **values: Any) -> None:
        user_id = values.pop("user_id", None)
        env_file = os.environ.get("DRIIVZ_ENV_FILE")
        if env_file:
            values.setdefault("_env_file", env_file)
        super().__init__(**values)
        self._load_personal_credentials(user_id)

    agent_root: Path | None = Field(
        default=None,
        validation_alias=AliasChoices("UBI_AI_AGENT_ROOT", "agent_root"),
    )
    base_url: str = DEFAULT_BASE_URL
    username: str | None = None
    password: SecretStr | None = None
    timeout_seconds: float = Field(default=30, gt=0)

    def validate_auth(self) -> None:
        if self.username and self.password:
            return
        message = (
            "Missing Driivz credentials. Set DRIIVZ_USERNAME and DRIIVZ_PASSWORD "
            "in the runtime environment or in the user's personal secrets file."
        )
        if self._credential_source_error:
            message = f"{message} Personal secrets lookup failed: {self._credential_source_error}"
        raise ValueError(message)

    def _load_personal_credentials(self, user_id: str | None) -> None:
        if self.username and self.password:
            return
        if not user_id:
            return
        if self.agent_root is None:
            self._credential_source_error = "UBI_AI_AGENT_ROOT is not configured."
            return
        try:
            values = load_personal_secret_values(
                agent_root=self.agent_root,
                user_id=user_id,
                required_keys=["DRIIVZ_USERNAME", "DRIIVZ_PASSWORD"],
            )
        except PersonalSecretsError as exc:
            self._credential_source_error = str(exc)
            return

        if not self.username:
            self.username = values["DRIIVZ_USERNAME"]
        if not self.password:
            self.password = SecretStr(values["DRIIVZ_PASSWORD"])
