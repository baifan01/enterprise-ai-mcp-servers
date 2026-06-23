# review-site-runtime-by-key

Review Driivz charger, site, status, and recent session context by key.

Wrapper: `driivz-read`

Mode: `read`

## When to use

Use when the user provides a company device ID or Driivz EVSE ID and needs CPMS runtime context, including charger identity, site/company details, current status, and optionally recent EV transactions.

## Parameters

| Name | Description |
| --- | --- |
| `key` | Required company device ID or Driivz EVSE ID. |
| `key_type` | One of: `auto`, `device_id`, `evse_id`. Defaults to `auto`; auto treats keys containing `*` as EVSE IDs and other values as company device IDs. |
| `user_id` | Runtime user id for personal secrets lookup. Wrappers bind this; the agent must not pass it directly. |
| `include_recent_sessions` | If true, also fetch recent EV transaction context for the resolved charger identity. Defaults to true. |

## Examples

```bash
driivz-read.sh review-site-runtime-by-key sebe1100000213
driivz-read.sh review-site-runtime-by-key "DE*UBI*E123456" --key-type evse_id
driivz-read.sh review-site-runtime-by-key sebe1100000213 --no-recent-sessions
```

## Output

JSON with requested key metadata, resolved flag, profile, location, site, site_program, status, optional recent_sessions, and errors.

## Safety

Read-only. Calls fixed Driivz REST endpoints with structured filters and does not modify CPMS data.
