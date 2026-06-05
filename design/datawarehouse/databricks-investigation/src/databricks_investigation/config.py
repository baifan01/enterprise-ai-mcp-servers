"""Configuration for Databricks investigation queries."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


def _load_dotenv_if_available(env_file: Optional[Path] = None) -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    load_dotenv(dotenv_path=env_file)


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value)


def _env_optional_float(name: str) -> Optional[float]:
    value = os.getenv(name)
    if value is None or value == "":
        return None
    return float(value)


def _env_optional_int(name: str) -> Optional[int]:
    value = os.getenv(name)
    if value is None or value == "":
        return None
    return int(value)


def quote_identifier(identifier: str) -> str:
    """将 catalog/schema/table 名包成 Databricks SQL 标识符，避免连字符等字符破坏 SQL。"""
    escaped = identifier.replace("`", "``")
    return f"`{escaped}`"


@dataclass(frozen=True)
class DatabricksSettings:
    """Databricks 调研配置集合，统一描述连接凭证、目标 schema 和查询窗口/超时参数。"""

    server_hostname: str
    http_path: str
    access_token: str
    catalog: str = "emobility-uc-prd"
    schema: str = "curated-emob-ubitricity-core"
    attempt_search_window_minutes: int = 30
    ocpp_time_buffer_seconds: int = 3
    ocpp_boundary_expand_ms: int = 500
    socket_timeout_seconds: Optional[float] = None
    retry_stop_after_attempts_count: Optional[int] = None
    retry_stop_after_attempts_duration_seconds: Optional[float] = None

    @classmethod
    def from_env(cls, env_file: Optional[str | Path] = None) -> "DatabricksSettings":
        """从 `.env` 或环境变量读取 Databricks 连接信息，并在缺少必需凭证时快速失败。"""
        _load_dotenv_if_available(Path(env_file) if env_file else None)

        missing = [
            name
            for name in (
                "DATABRICKS_SERVER_HOSTNAME",
                "DATABRICKS_HTTP_PATH",
                "DATABRICKS_TOKEN",
            )
            if not os.getenv(name)
        ]
        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"Missing required Databricks environment variables: {joined}")

        return cls(
            server_hostname=os.environ["DATABRICKS_SERVER_HOSTNAME"],
            http_path=os.environ["DATABRICKS_HTTP_PATH"],
            access_token=os.environ["DATABRICKS_TOKEN"],
            catalog=os.getenv("DATABRICKS_CATALOG", cls.catalog),
            schema=os.getenv("DATABRICKS_SCHEMA", cls.schema),
            attempt_search_window_minutes=_env_int(
                "DATABRICKS_ATTEMPT_SEARCH_WINDOW_MINUTES",
                cls.attempt_search_window_minutes,
            ),
            ocpp_time_buffer_seconds=_env_int(
                "DATABRICKS_OCPP_TIME_BUFFER_SECONDS",
                cls.ocpp_time_buffer_seconds,
            ),
            ocpp_boundary_expand_ms=_env_int(
                "DATABRICKS_OCPP_BOUNDARY_EXPAND_MS",
                cls.ocpp_boundary_expand_ms,
            ),
            socket_timeout_seconds=_env_optional_float("DATABRICKS_SOCKET_TIMEOUT_SECONDS"),
            retry_stop_after_attempts_count=_env_optional_int(
                "DATABRICKS_RETRY_STOP_AFTER_ATTEMPTS_COUNT"
            ),
            retry_stop_after_attempts_duration_seconds=_env_optional_float(
                "DATABRICKS_RETRY_STOP_AFTER_ATTEMPTS_DURATION_SECONDS"
            ),
        )

    def table(self, name: str) -> str:
        """生成当前 catalog/schema 下的全限定表名，供查询代码安全引用目标视图。"""
        return ".".join(
            [
                quote_identifier(self.catalog),
                quote_identifier(self.schema),
                quote_identifier(name),
            ]
        )
