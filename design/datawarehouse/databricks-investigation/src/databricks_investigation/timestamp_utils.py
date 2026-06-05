"""Timestamp parsing helpers."""

from __future__ import annotations

import datetime as dt
from typing import Any, Optional


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


def coerce_datetime(value: Any) -> Optional[dt.datetime]:
    """将 Databricks 返回值、字符串或 date 对象规整成 naive datetime，供时间窗口查询和比较使用。"""
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value
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


def seconds_between(later: dt.datetime, earlier: dt.datetime) -> float:
    """计算两个时间点之间的秒级差值，用于 OCPP offset 和 attempt 间隔判断。"""
    return (later - earlier).total_seconds()
