# query-charging-attempts

Query charging attempts for one device or EVSE in a time window.

Wrapper: `databricks-read`

Mode: `read`

## When to use

Use when the user needs charging session attempt context for a known internal SSO ID or external EVSE ID in a bounded time range, including adjacent attempts that may belong to the same user-level journey.

## Parameters

| Name | Description |
| --- | --- |
| `time_from` | Required inclusive start timestamp. Accepts ISO-8601 strings or datetime values. |
| `time_to` | Required inclusive end timestamp. Accepts ISO-8601 strings or datetime values. |
| `sso_id` | Optional internal device SSO ID. Provide either `sso_id` or `evse_id`. |
| `evse_id` | Optional external EVSE ID. Provide either `evse_id` or `sso_id`; the query resolves it to an internal SSO ID when needed. |
| `user_id` | Runtime user id for personal secrets lookup. Wrappers bind this; the agent must not pass it directly. |

## Examples

```bash
databricks-read.sh query-charging-attempts --sso-id suby1100012048 --time-from 2026-06-03T19:00:00Z --time-to 2026-06-03T20:00:00Z
databricks-read.sh query-charging-attempts --evse-id DE*UBI*E123456 --time-from 2026-06-03T19:00:00Z --time-to 2026-06-03T20:00:00Z
```

## Output

JSON with query metadata, raw_attempt_count, merged_attempt_count, raw_attempts, merged_attempts, had_adjacent_merge, and errors.

## Safety

Read-only. Executes fixed Databricks SQL through structured parameters and does not accept arbitrary SQL.
