"""Simplified OCPP silence gap analysis for device online status.

This module contains only pure timeline logic. It does not query Databricks,
read settings, or know about MCP transport. The temporary rule is intentionally
small: a long silence is suspicious when the event immediately before the
silence was not a charging-related OCPP event. The only charging-related events
for this temporary rule are StartTransaction and StatusNotification(Charging).
"""

from __future__ import annotations

import datetime as dt
import json
import re
from collections.abc import Iterable

from mcp_datawarehouse.models import OCPPEvent, OfflinePeriod

HEARTBEAT = "Heartbeat"
START_TRANSACTION = "StartTransaction"
STATUS_NOTIFICATION = "StatusNotification"
CHARGING_STATUS = "Charging"
OFFLINE_GAP_REASON = "non_charging_ocpp_gap_exceeded_threshold"


def analyze_heartbeat_gaps(
    events: Iterable[OCPPEvent],
    *,
    analysis_start: dt.datetime,
    analysis_end: dt.datetime,
    offline_threshold_seconds: int,
) -> list[OfflinePeriod]:
    """Return suspicious OCPP silence gaps clipped to the requested window."""

    if analysis_start > analysis_end:
        raise ValueError("analysis_start must be earlier than or equal to analysis_end")
    if offline_threshold_seconds <= 0:
        raise ValueError("offline_threshold_seconds must be positive")

    sorted_events = _dedupe_events(
        sorted(events, key=lambda event: (event.operation_timestamp, event.ocpp_message_type))
    )
    previous_event: OCPPEvent | None = None
    periods: list[OfflinePeriod] = []

    for event in sorted_events:
        if previous_event is not None and not is_charging_related_event(previous_event):
            gap_seconds = int(
                (event.operation_timestamp - previous_event.operation_timestamp).total_seconds()
            )
            if gap_seconds > offline_threshold_seconds:
                clipped = _clip_period(
                    previous_event.operation_timestamp,
                    event.operation_timestamp,
                    analysis_start,
                    analysis_end,
                )
                if clipped is not None:
                    clipped_start, clipped_restore = clipped
                    periods.append(
                        OfflinePeriod(
                            sso_id=event.sso_id,
                            offline_start=clipped_start,
                            offline_restore=clipped_restore,
                            duration_seconds=int((clipped_restore - clipped_start).total_seconds()),
                            reason=OFFLINE_GAP_REASON,
                            evidence={
                                "raw_offline_start": previous_event.operation_timestamp.isoformat(),
                                "raw_offline_restore": event.operation_timestamp.isoformat(),
                                "previous_event_time": (
                                    previous_event.operation_timestamp.isoformat()
                                ),
                                "previous_event_type": previous_event.ocpp_message_type,
                                "restore_event_time": event.operation_timestamp.isoformat(),
                                "restore_event_type": event.ocpp_message_type,
                                "threshold_seconds": offline_threshold_seconds,
                                "gap_seconds": gap_seconds,
                                "clipped_to_requested_window": (
                                    clipped_start != previous_event.operation_timestamp
                                    or clipped_restore != event.operation_timestamp
                                ),
                            },
                        )
                    )

        previous_event = event

    return periods


def is_charging_related_event(event: OCPPEvent) -> bool:
    """Return whether an event should suppress a following long silence."""

    if event.ocpp_message_type == START_TRANSACTION:
        return True
    if event.ocpp_message_type != STATUS_NOTIFICATION:
        return False
    return _status_notification_status(event.ocpp_request_body) == CHARGING_STATUS


def offline_period_to_dict(period: OfflinePeriod) -> dict[str, object]:
    """Return a JSON-friendly representation of an offline period."""

    return {
        "sso_id": period.sso_id,
        "offline_start": period.offline_start.isoformat(),
        "offline_restore": period.offline_restore.isoformat(),
        "duration_seconds": period.duration_seconds,
        "reason": period.reason,
        "evidence": period.evidence,
    }


def _clip_period(
    start: dt.datetime,
    end: dt.datetime,
    window_start: dt.datetime,
    window_end: dt.datetime,
) -> tuple[dt.datetime, dt.datetime] | None:
    clipped_start = max(start, window_start)
    clipped_end = min(end, window_end)
    if clipped_start >= clipped_end:
        return None
    return clipped_start, clipped_end


def _status_notification_status(request_body: str | None) -> str | None:
    if not request_body:
        return None

    try:
        parsed = json.loads(request_body)
    except json.JSONDecodeError:
        parsed = None

    candidates = parsed if isinstance(parsed, list) else [parsed]
    for item in candidates:
        if isinstance(item, dict) and isinstance(item.get("status"), str):
            return item["status"]

    match = re.search(r'"status"\s*:\s*"([^"]+)"', request_body)
    return match.group(1) if match else None


def _dedupe_events(events: list[OCPPEvent]) -> list[OCPPEvent]:
    deduped: list[OCPPEvent] = []
    seen: set[tuple[str, dt.datetime, str]] = set()
    for event in events:
        key = (event.sso_id, event.operation_timestamp, event.ocpp_message_type)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(event)
    return deduped
