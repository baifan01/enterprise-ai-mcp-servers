"""Legacy-compatible Heartbeat gap analysis for device online status.

This module contains only pure timeline logic. It does not query Databricks,
read settings, or know about MCP transport. The rule intentionally mirrors the
old investigation script: a Heartbeat gap is suspicious only when the previous
Heartbeat is also the most recent OCPP event, meaning no other OCPP activity was
seen between the two Heartbeats. More complete BI or charging-session-aware
logic should live in a separate analyzer instead of expanding this temporary
compatibility rule.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable

from mcp_datawarehouse.models import OCPPEvent, OfflinePeriod

HEARTBEAT = "Heartbeat"
HEARTBEAT_GAP_REASON = "heartbeat_gap_without_intermediate_ocpp_event"


def analyze_heartbeat_gaps(
    events: Iterable[OCPPEvent],
    *,
    analysis_start: dt.datetime,
    analysis_end: dt.datetime,
    offline_threshold_seconds: int,
) -> list[OfflinePeriod]:
    """Return suspicious Heartbeat gaps clipped to the requested window."""

    if analysis_start > analysis_end:
        raise ValueError("analysis_start must be earlier than or equal to analysis_end")
    if offline_threshold_seconds <= 0:
        raise ValueError("offline_threshold_seconds must be positive")

    sorted_events = _dedupe_events(
        sorted(events, key=lambda event: (event.operation_timestamp, event.ocpp_message_type))
    )
    last_heartbeat_time: dt.datetime | None = None
    last_event_time: dt.datetime | None = None
    last_event_type: str | None = None
    periods: list[OfflinePeriod] = []

    for event in sorted_events:
        event_time = event.operation_timestamp
        event_type = event.ocpp_message_type

        if event_type == HEARTBEAT:
            if last_heartbeat_time is not None:
                gap_seconds = int((event_time - last_heartbeat_time).total_seconds())
                if (
                    gap_seconds > offline_threshold_seconds
                    and last_heartbeat_time == last_event_time
                ):
                    clipped = _clip_period(
                        last_heartbeat_time,
                        event_time,
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
                                duration_seconds=int(
                                    (clipped_restore - clipped_start).total_seconds()
                                ),
                                reason=HEARTBEAT_GAP_REASON,
                                evidence={
                                    "raw_offline_start": last_heartbeat_time.isoformat(),
                                    "raw_offline_restore": event_time.isoformat(),
                                    "previous_heartbeat_time": last_heartbeat_time.isoformat(),
                                    "restore_heartbeat_time": event_time.isoformat(),
                                    "threshold_seconds": offline_threshold_seconds,
                                    "gap_seconds": gap_seconds,
                                    "previous_event_type": last_event_type,
                                    "clipped_to_requested_window": (
                                        clipped_start != last_heartbeat_time
                                        or clipped_restore != event_time
                                    ),
                                },
                            )
                        )
            last_heartbeat_time = event_time

        last_event_time = event_time
        last_event_type = event_type

    return periods


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
