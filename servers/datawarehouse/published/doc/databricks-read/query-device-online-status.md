# query-device-online-status

Analyze Heartbeat gaps to identify device offline periods.

Wrapper: `databricks-read`

Mode: `read`

## When to use

Use when the user asks whether a charge point was online or offline in a specific time window, or needs Heartbeat gap evidence compatible with the legacy online-status analysis.

## Parameters

| Name | Description |
| --- | --- |
| `sso_id` | Required internal device SSO ID. |
| `time_from` | Required inclusive start timestamp. Accepts ISO-8601 strings or datetime values. |
| `time_to` | Required inclusive end timestamp. Accepts ISO-8601 strings or datetime values. |
| `heartbeat_interval_seconds` | Expected Heartbeat interval in seconds. Defaults to 900. |
| `missed_heartbeat_tolerance` | Number of missed Heartbeats tolerated before flagging an offline gap. Defaults to 1. |
| `recent_end_grace_seconds` | Skip querying the next event when `time_to` is this close to now. Defaults to 1800. |

## Examples

```bash
databricks-read.sh query-device-online-status --sso-id suby1100012048 --time-from 2026-06-03T19:00:00Z --time-to 2026-06-03T20:00:00Z
databricks-read.sh query-device-online-status --sso-id suby1100012048 --time-from 2026-06-03T19:00:00Z --time-to 2026-06-03T20:00:00Z --heartbeat-interval-seconds 900 --missed-heartbeat-tolerance 2
```

## Output

JSON with query metadata, coverage, has_offline, offline_periods, event_count_in_window, heartbeat_count_in_window, summary, and errors.

## Safety

Read-only. Executes fixed Databricks SQL through structured parameters and infers offline periods only from events in the requested range.
