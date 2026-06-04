"""Timestamp parsing helpers for Databricks query inputs and rows."""

from __future__ import annotations

import datetime as dt
from typing import Any

SUPPORTED_FORMATS = (
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d",
    "%Y/%m/%d %H:%M:%S",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
)


def coerce_datetime(value: Any) -> dt.datetime | None:
    """Normalize Databricks timestamps and user strings to naive datetimes."""

    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, dt.date):
        return dt.datetime.combine(value, dt.time.min)
    if not isinstance(value, str):
        return value

    cleaned = value.strip().replace(" GMT", "")
    if not cleaned:
        return None

    try:
        return dt.datetime.fromisoformat(cleaned.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        pass

    normalized = cleaned.replace("T", " ")
    for fmt in SUPPORTED_FORMATS:
        try:
            return dt.datetime.strptime(normalized, fmt)
        except ValueError:
            continue

    raise ValueError(f"Unsupported timestamp format: {value}")
