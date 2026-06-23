# create-wiki-child-page

Create a Confluence child page under a required parent page or folder.

Wrapper: `atlassian-write`

Mode: `write`

## When to use

Use when the user explicitly wants to create a new Confluence page under a known parent page or folder and provides Markdown body content.

## Parameters

| Name | Description |
| --- | --- |
| `parent_url` | Required Confluence browser URL for a parent page or folder. |
| `title` | Required page title. |
| `body_markdown` | Required Markdown body using the supported subset. |
| `mark_agent_friendly` | If true, also add the `ubitricity-agent-friendly` label. Defaults to false. The `ubitricity-ai-generated` label is always attempted. |
| `user_id` | Runtime user id for personal secrets lookup. Wrappers bind this; the agent must not pass it directly. |

## Examples

```bash
atlassian-write.sh create-wiki-child-page --parent-url "https://example.atlassian.net/wiki/spaces/UM/folder/123456789" --title "Agent Runbook" --body-markdown "# Runbook" --mark-agent-friendly
```

## Output

JSON with created page id, title, parent_id, parent_type, space_id, web_url, labels, conversion_warnings, warnings, and errors.

## Safety

Write operation. Creates a Confluence page and attempts to add labels. Does not accept arbitrary HTML or storage XHTML; Markdown is converted through the bounded internal converter.
