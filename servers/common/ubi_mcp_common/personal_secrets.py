"""Resolve user-scoped personal secrets for local tool adapters.

This module owns the filesystem rules for the local tool permission model. Tool
settings pass in an agent root and user id; this helper validates that the user
id cannot escape the user directory, reads the user's personal secrets env file,
and returns only requested keys. Business services and clients should not know
where personal secret files live.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path
from typing import Iterable

PERSONAL_SECRETS_FILENAME = "personal-secrets.env"
_USER_ID_PATTERN = re.compile(r"^[A-Za-z0-9._@+-]+$")


class PersonalSecretsError(ValueError):
    """Raised when user-scoped personal secrets cannot be safely resolved."""


def personal_secrets_path(agent_root: str | Path, user_id: str) -> Path:
    """Return the personal secrets env path for a validated user id."""

    normalized_user_id = _validate_user_id(user_id)
    root = Path(agent_root).expanduser().resolve()
    path = (root / "users" / normalized_user_id / "secrets" / PERSONAL_SECRETS_FILENAME).resolve()
    users_root = (root / "users").resolve()
    try:
        path.relative_to(users_root)
    except ValueError as exc:
        raise PersonalSecretsError("Resolved personal secrets path escapes users root.") from exc
    return path


def load_personal_secret_values(
    *,
    agent_root: str | Path,
    user_id: str,
    required_keys: Iterable[str],
) -> dict[str, str]:
    """Load required values from a user's personal secrets env file."""

    keys = list(required_keys)
    path = personal_secrets_path(agent_root, user_id)
    if not path.is_file():
        raise PersonalSecretsError(f"Personal secrets file does not exist: {path}")

    values = _read_env_file(path)
    missing = [key for key in keys if not values.get(key)]
    if missing:
        joined = ", ".join(missing)
        raise PersonalSecretsError(f"Personal secrets file is missing required keys: {joined}")
    return {key: values[key] for key in keys}


def _validate_user_id(user_id: str) -> str:
    normalized = user_id.strip()
    if not normalized:
        raise PersonalSecretsError("user_id must not be empty.")
    if not _USER_ID_PATTERN.fullmatch(normalized):
        raise PersonalSecretsError("user_id contains unsupported characters.")
    return normalized


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise PersonalSecretsError(f"Failed to read personal secrets file: {path}") from exc

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").strip()
        if "=" not in line:
            raise PersonalSecretsError(
                f"Invalid personal secrets line {line_number}: expected KEY=VALUE."
            )
        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not key:
            raise PersonalSecretsError(f"Invalid personal secrets line {line_number}: empty key.")
        values[key] = _parse_env_value(raw_value.strip())
    return values


def _parse_env_value(raw_value: str) -> str:
    if not raw_value:
        return ""
    if raw_value[0] in {"'", '"'}:
        try:
            parsed = shlex.split(raw_value, comments=False, posix=True)
        except ValueError:
            return raw_value
        return parsed[0] if parsed else ""

    marker = " #"
    if marker in raw_value:
        return raw_value.split(marker, 1)[0].rstrip()
    return raw_value
