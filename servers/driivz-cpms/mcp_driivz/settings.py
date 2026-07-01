"""Driivz CPMS server settings.

This module is the only place that reads Driivz runtime configuration. ubi-ai
broker injects credentials into the process environment; standalone development
can still use the local .env file.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

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

    def __init__(self, **values: Any) -> None:
        env_file = os.environ.get("DRIIVZ_ENV_FILE")
        if env_file:
            values.setdefault("_env_file", env_file)
        super().__init__(**values)

    base_url: str = DEFAULT_BASE_URL
    username: str | None = None
    password: SecretStr | None = None
    timeout_seconds: float = Field(default=30, gt=0)

    def validate_auth(self) -> None:
        if self.username and self.password:
            return
        raise ValueError(
            "Missing Driivz credentials. Set DRIIVZ_USERNAME and "
            "DRIIVZ_PASSWORD in the runtime environment."
        )
