# read-wiki-page

Read one Confluence page and return normalized page content.

Wrapper: `atlassian-read`

Mode: `read`

## When to use

Use when the user provides a Confluence page id or URL and the agent needs the full page body, page metadata, and optionally root footer comments.

## Parameters

| Name | Description |
| --- | --- |
| `page_id` | Optional numeric Confluence page id. Exactly one of `page_id` or `page_url` must be provided. |
| `page_url` | Optional browser URL copied from Confluence. Exactly one of `page_id` or `page_url` must be provided. |
| `include_footer_comments` | If true, also read root footer comments. Defaults to false. |
| `user_id` | Runtime user id for personal secrets lookup. Wrappers bind this; the agent must not pass it directly. |

## Examples

```bash
atlassian-read.sh read-wiki-page --page-id 5781061778
atlassian-read.sh read-wiki-page --page-url "https://example.atlassian.net/wiki/spaces/UM/pages/5781061778/Page"
atlassian-read.sh read-wiki-page --page-id 5781061778 --include-footer-comments
```

## Output

JSON with normalized page id, parent_id, space_id, title, owner, author, version_number, storage body, optional footer_comments, web_url, warnings, and errors.

## Safety

Read-only. Uses fixed `body-format=storage` internally and does not expose arbitrary Confluence API parameters.
