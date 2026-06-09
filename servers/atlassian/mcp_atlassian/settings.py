"""Atlassian settings.

This module is the only place that reads Atlassian environment variables and
user personal secrets. Business services receive settings objects and never
reach into env directly.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import AliasChoices, Field, PrivateAttr, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from ubi_mcp_common import PersonalSecretsError, load_personal_secret_values

PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = PROJECT_DIR / ".env"


class AtlassianSettings(BaseSettings):
    """Runtime configuration for Atlassian REST API calls."""

    model_config = SettingsConfigDict(
        env_prefix="ATLASSIAN_",
        env_file=DEFAULT_ENV_FILE,
        extra="ignore",
        populate_by_name=True,
    )

    _credential_source_error: str | None = PrivateAttr(default=None)

    def __init__(self, **values: Any) -> None:
        user_id = values.pop("user_id", None)
        env_file = os.environ.get("ATLASSIAN_ENV_FILE")
        if env_file:
            values.setdefault("_env_file", env_file)
        super().__init__(**values)
        self._load_personal_credentials(user_id)

    agent_root: Path | None = Field(
        default=None,
        validation_alias=AliasChoices("UBI_AI_AGENT_ROOT", "agent_root"),
    )
    base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ATLASSIAN_BASE_URL", "JIRA_BASE_URL"),
    )
    email: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ATLASSIAN_EMAIL", "JIRA_EMAIL"),
    )
    api_token: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("ATLASSIAN_API_TOKEN", "JIRA_API_TOKEN"),
    )
    timeout_seconds: float = Field(default=30, gt=0)

    def validate_auth(self) -> None:
        if self.base_url and self.email and self.api_token:
            return
        message = (
            "Missing Atlassian credentials. Set ATLASSIAN_BASE_URL, ATLASSIAN_EMAIL, "
            "and ATLASSIAN_API_TOKEN in the runtime environment or in the user's "
            "personal secrets file."
        )
        if self._credential_source_error:
            message = f"{message} Personal secrets lookup failed: {self._credential_source_error}"
        raise ValueError(message)

    def _load_personal_credentials(self, user_id: str | None) -> None:
        if self.base_url and self.email and self.api_token:
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
                required_keys=[
                    "ATLASSIAN_BASE_URL",
                    "ATLASSIAN_EMAIL",
                    "ATLASSIAN_API_TOKEN",
                ],
            )
        except PersonalSecretsError as exc:
            self._credential_source_error = str(exc)
            return

        if not self.base_url:
            self.base_url = values["ATLASSIAN_BASE_URL"]
        if not self.email:
            self.email = values["ATLASSIAN_EMAIL"]
        if not self.api_token:
            self.api_token = SecretStr(values["ATLASSIAN_API_TOKEN"])
