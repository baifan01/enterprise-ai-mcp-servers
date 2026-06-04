"""Data warehouse settings.

This module is the only place that reads data warehouse environment variables.
Business services receive a Settings object and never reach into env directly.
Table naming and connector tuning live here so query modules can stay focused on
domain-level Databricks reads.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = PROJECT_DIR / ".env"
DEFAULT_CATALOG = "emobility-uc-prd"
DEFAULT_SCHEMA = "curated-emob-ubitricity-core"


def quote_identifier(identifier: str) -> str:
    """Return a Databricks SQL identifier quoted for catalog/schema names."""

    return f"`{identifier.replace('`', '``')}`"


class DatawarehouseSettings(BaseSettings):
    """Runtime configuration for Databricks data warehouse queries."""

    model_config = SettingsConfigDict(
        env_prefix="DATAWAREHOUSE_",
        env_file=DEFAULT_ENV_FILE,
        extra="ignore",
        populate_by_name=True,
    )

    def __init__(self, **values: Any) -> None:
        env_file = os.environ.get("DATAWAREHOUSE_ENV_FILE")
        if env_file:
            values.setdefault("_env_file", env_file)
        super().__init__(**values)

    databricks_server_hostname: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "DATAWAREHOUSE_DATABRICKS_SERVER_HOSTNAME",
            "DATABRICKS_SERVER_HOSTNAME",
        ),
    )
    databricks_http_path: str | None = Field(
        default=None,
        validation_alias=AliasChoices("DATAWAREHOUSE_DATABRICKS_HTTP_PATH", "DATABRICKS_HTTP_PATH"),
    )
    databricks_token: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("DATAWAREHOUSE_DATABRICKS_TOKEN", "DATABRICKS_TOKEN"),
    )
    databricks_catalog: str = Field(
        default=DEFAULT_CATALOG,
        validation_alias=AliasChoices("DATAWAREHOUSE_DATABRICKS_CATALOG", "DATABRICKS_CATALOG"),
    )
    databricks_schema: str = Field(
        default=DEFAULT_SCHEMA,
        validation_alias=AliasChoices("DATAWAREHOUSE_DATABRICKS_SCHEMA", "DATABRICKS_SCHEMA"),
    )
    attempt_search_window_minutes: int = Field(
        default=30,
        gt=0,
        validation_alias=AliasChoices(
            "DATAWAREHOUSE_ATTEMPT_SEARCH_WINDOW_MINUTES",
            "DATABRICKS_ATTEMPT_SEARCH_WINDOW_MINUTES",
        ),
    )
    ocpp_time_buffer_seconds: int = Field(
        default=3,
        ge=0,
        validation_alias=AliasChoices(
            "DATAWAREHOUSE_OCPP_TIME_BUFFER_SECONDS",
            "DATABRICKS_OCPP_TIME_BUFFER_SECONDS",
        ),
    )
    ocpp_boundary_expand_ms: int = Field(
        default=500,
        ge=0,
        validation_alias=AliasChoices(
            "DATAWAREHOUSE_OCPP_BOUNDARY_EXPAND_MS",
            "DATABRICKS_OCPP_BOUNDARY_EXPAND_MS",
        ),
    )
    socket_timeout_seconds: float | None = Field(
        default=None,
        gt=0,
        validation_alias=AliasChoices(
            "DATAWAREHOUSE_SOCKET_TIMEOUT_SECONDS",
            "DATABRICKS_SOCKET_TIMEOUT_SECONDS",
        ),
    )
    retry_stop_after_attempts_count: int | None = Field(
        default=None,
        gt=0,
        validation_alias=AliasChoices(
            "DATAWAREHOUSE_RETRY_STOP_AFTER_ATTEMPTS_COUNT",
            "DATABRICKS_RETRY_STOP_AFTER_ATTEMPTS_COUNT",
        ),
    )
    retry_stop_after_attempts_duration_seconds: float | None = Field(
        default=None,
        gt=0,
        validation_alias=AliasChoices(
            "DATAWAREHOUSE_RETRY_STOP_AFTER_ATTEMPTS_DURATION_SECONDS",
            "DATABRICKS_RETRY_STOP_AFTER_ATTEMPTS_DURATION_SECONDS",
        ),
    )

    def validate_databricks_auth(self) -> None:
        if self.databricks_server_hostname and self.databricks_http_path and self.databricks_token:
            return
        raise ValueError(
            "Missing Databricks credentials. Set DATABRICKS_SERVER_HOSTNAME, "
            "DATABRICKS_HTTP_PATH, and DATABRICKS_TOKEN in the environment or "
            "in DATAWAREHOUSE_ENV_FILE."
        )

    def table(self, name: str) -> str:
        return ".".join(
            [
                quote_identifier(self.databricks_catalog),
                quote_identifier(self.databricks_schema),
                quote_identifier(name),
            ]
        )
