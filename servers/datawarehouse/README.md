# Data Warehouse Core Service

Databricks data warehouse query core for charging attempts and OCPP event
sequence investigation. This project intentionally keeps MCP packaging out of
scope for now; the current entrypoints are async service functions and a CLI for
Codex/local validation.

## CLI

```bash
uv run python -m mcp_datawarehouse.cli query-charging-attempts \
  --sso-id suby1100012048 \
  --time-from 2026-06-03T19:00:00Z \
  --time-to 2026-06-03T20:00:00Z \
  --pretty

uv run python -m mcp_datawarehouse.cli query-ocpp-sequence \
  --sso-id suby1100012048 \
  --time-from 2026-06-03T19:20:00Z \
  --time-to 2026-06-03T19:30:00Z \
  --pretty
```

Set credentials in `servers/datawarehouse/.env` or point
`DATAWAREHOUSE_ENV_FILE` at an env file. The service accepts the existing
investigation-style `DATABRICKS_*` keys.
