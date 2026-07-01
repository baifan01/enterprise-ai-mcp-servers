"""Atlassian settings.

This module is the only place that reads Atlassian runtime configuration.
Business services receive settings objects and never reach into env directly.
Credentials are supplied through the process environment by ubi-ai broker, with
an optional local .env override for standalone development.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

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

    def __init__(self, **values: Any) -> None:
        env_file = os.environ.get("ATLASSIAN_ENV_FILE")
        if env_file:
            values.setdefault("_env_file", env_file)
        super().__init__(**values)

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
        raise ValueError(
            "Missing Atlassian credentials. Set ATLASSIAN_BASE_URL, "
            "ATLASSIAN_EMAIL, and ATLASSIAN_API_TOKEN in the runtime environment."
        )
