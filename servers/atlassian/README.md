# Atlassian Core Service

Formal Atlassian local-tool backend for Jira and Confluence capabilities.

The first implementation focuses on Confluence wiki pages:

- `read-wiki-page`
- `search-wiki-pages`
- `create-wiki-child-page`

Credentials follow the local tool broker configuration model:

```text
ubi-ai broker
  -> reads user/system scope config from DB
  -> injects environment variables into the tool subprocess
AtlassianSettings
  -> reads ATLASSIAN_BASE_URL, ATLASSIAN_EMAIL, ATLASSIAN_API_TOKEN from env
```

`ATLASSIAN_TIMEOUT_SECONDS` is a non-secret runtime setting and may live in this
service's local `.env`.
