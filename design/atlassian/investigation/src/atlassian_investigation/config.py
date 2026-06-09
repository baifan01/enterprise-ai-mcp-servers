"""Configuration for Atlassian investigation scripts.

This module is the only investigation layer that reads environment variables or
`.env` files. Client and query modules receive a settings object so the future
service implementation can keep the same boundary.
"""

from __future__ import annotations

import os
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

PROJECT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_ENV_FILE = PROJECT_DIR / ".env"


def _load_dotenv(env_file: Optional[str | Path]) -> None:
    path = Path(env_file) if env_file else DEFAULT_ENV_FILE
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_env_line(raw_line)
        if parsed is None:
            continue
        key, value = parsed
        os.environ.setdefault(key, value)


def _parse_env_line(raw_line: str) -> tuple[str, str] | None:
    line = raw_line.strip()
    if not line or line.startswith("#"):
        return None
    if line.startswith("export "):
        line = line.removeprefix("export ").strip()
    if "=" not in line:
        return None

    key, raw_value = line.split("=", 1)
    key = key.strip()
    if not key:
        return None
    return key, _parse_env_value(raw_value.strip())


def _parse_env_value(raw_value: str) -> str:
    if not raw_value:
        return ""
    if raw_value[0] in {"'", '"'}:
        try:
            parsed = shlex.split(raw_value, comments=False, posix=True)
        except ValueError:
            return raw_value
        return parsed[0] if parsed else ""
    if " #" in raw_value:
        return raw_value.split(" #", 1)[0].rstrip()
    return raw_value


def _first_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def _env_int(name: str, fallback_name: str, default: int) -> int:
    value = _first_env(name, fallback_name)
    if value is None or value == "":
        return default
    return int(value)


@dataclass(frozen=True)
class AtlassianSettings:
    """Atlassian Cloud connection settings for investigation API calls."""

    base_url: str
    email: str
    api_token: str
    timeout_seconds: int = 30

    @classmethod
    def from_env(cls, env_file: Optional[str | Path] = None) -> "AtlassianSettings":
        """Read Atlassian credentials from `.env` or current environment."""

        _load_dotenv(env_file)

        base_url = _first_env("ATLASSIAN_BASE_URL", "JIRA_BASE_URL")
        email = _first_env("ATLASSIAN_EMAIL", "JIRA_EMAIL")
        api_token = _first_env("ATLASSIAN_API_TOKEN", "JIRA_API_TOKEN")
        missing = [
            name
            for name, value in {
                "ATLASSIAN_BASE_URL or JIRA_BASE_URL": base_url,
                "ATLASSIAN_EMAIL or JIRA_EMAIL": email,
                "ATLASSIAN_API_TOKEN or JIRA_API_TOKEN": api_token,
            }.items()
            if not value
        ]
        if missing:
            raise ValueError(f"Missing required Atlassian environment variables: {', '.join(missing)}")

        return cls(
            base_url=str(base_url).rstrip("/"),
            email=str(email),
            api_token=str(api_token),
            timeout_seconds=_env_int("ATLASSIAN_TIMEOUT_SECONDS", "JIRA_TIMEOUT_SECONDS", 30),
        )
