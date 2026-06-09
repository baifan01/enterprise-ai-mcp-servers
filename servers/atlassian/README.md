# Atlassian Core Service

Formal Atlassian local-tool backend for Jira and Confluence capabilities.

The first implementation focuses on Confluence wiki pages:

- `read-wiki-page`
- `search-wiki-pages`
- `create-wiki-child-page`

Credentials follow the local tool permission model:

```text
AtlassianSettings(user_id=...)
  -> UBI_AI_AGENT_ROOT/users/<user_id>/secrets/personal-secrets.env
  -> ATLASSIAN_BASE_URL, ATLASSIAN_EMAIL, ATLASSIAN_API_TOKEN
```

`ATLASSIAN_TIMEOUT_SECONDS` is a non-secret runtime setting and may live in this
service's local `.env`.
