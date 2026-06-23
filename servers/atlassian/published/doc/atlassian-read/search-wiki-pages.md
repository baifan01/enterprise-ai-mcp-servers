# search-wiki-pages

Search Confluence pages by title or body text.

Wrapper: `atlassian-read`

Mode: `read`

## When to use

Use when the user wants to find wiki pages by keywords, optionally under a parent page. Use this before `read-wiki-page` when the page id or URL is not known.

## Parameters

| Name | Description |
| --- | --- |
| `text` | Optional keywords. Supports one string or multiple terms. |
| `search_field` | One of: `text`, `title`. Defaults to `text`. |
| `parent_url` | Optional Confluence browser URL. Limits search to the parent page and all descendants. |
| `agent_friendly_only` | If true, only search pages labeled `ubitricity-agent-friendly`. |
| `match` | One of: `all`, `any`. Defaults to `all`. |
| `max_results` | Maximum number of results. Capped at 50. |
| `user_id` | Runtime user id for personal secrets lookup. Wrappers bind this; the agent must not pass it directly. |

## Examples

```bash
atlassian-read.sh search-wiki-pages "design system" --search-field title
atlassian-read.sh search-wiki-pages "runbook" --agent-friendly-only
atlassian-read.sh search-wiki-pages "release" --parent-url "https://example.atlassian.net/wiki/spaces/UM/pages/123456789/Page"
```

## Output

JSON with query metadata, result_count, page summaries, warnings, and errors.

## Safety

Read-only. Does not expose arbitrary CQL. The service builds CQL from structured parameters and always limits content type to page.
