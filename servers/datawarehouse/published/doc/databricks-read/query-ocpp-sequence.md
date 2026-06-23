# query-ocpp-sequence

Query a compact OCPP event sequence for one device window.

Wrapper: `databricks-read`

Mode: `read`

## When to use

Use when the user needs chronological OCPP operation evidence for a device in a bounded time range, especially to inspect start, stop, authorization, status notification, or transaction behavior around an incident.

## Parameters

| Name | Description |
| --- | --- |
| `sso_id` | Required internal device SSO ID. |
| `time_from` | Required inclusive start timestamp. Accepts ISO-8601 strings or datetime values. |
| `time_to` | Required inclusive end timestamp. Accepts ISO-8601 strings or datetime values. |
| `user_id` | Runtime user id for personal secrets lookup. Wrappers bind this; the agent must not pass it directly. |
| `include_heartbeats` | If true, include Heartbeat events in the sequence. Defaults to false to keep output focused. |
| `include_raw_payload` | If true, include bounded raw request and response payload snippets. Defaults to false. |
| `max_payload_chars` | Maximum raw payload characters per request or response when raw payloads are included. Defaults to 1200. |

## Examples

```bash
databricks-read.sh query-ocpp-sequence --sso-id suby1100012048 --time-from 2026-06-03T19:20:00Z --time-to 2026-06-03T19:30:00Z
databricks-read.sh query-ocpp-sequence --sso-id suby1100012048 --time-from 2026-06-03T19:20:00Z --time-to 2026-06-03T19:30:00Z --include-raw-payload --max-payload-chars 2000
```

## Output

JSON with query metadata, event_count, event_type_counts, ordered events, optional bounded payload snippets, and errors.

## Safety

Read-only. Executes fixed Databricks SQL through structured parameters. Raw payload output is disabled by default and bounded when enabled.
