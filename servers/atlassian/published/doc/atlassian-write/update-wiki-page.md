# update-wiki-page

Replace one Confluence page body using a required page URL.

Wrapper: `atlassian-write`

Mode: `write`

## When to use

Use when the user explicitly wants to replace the content of an existing Confluence page and provides the page browser URL plus new Markdown body.

## Parameters

| Name | Description |
| --- | --- |
| `page_url` | Required Confluence browser URL for the page to update. Folder URLs are not accepted. |
| `body_markdown` | Required Markdown body using the supported subset. It replaces the previous page body. |
| `title` | Optional replacement title. If omitted, the current page title is preserved. |
| `version_message` | Optional Confluence version message. |

## Examples

```bash
atlassian-write.sh update-wiki-page --page-url "https://example.atlassian.net/wiki/spaces/UM/pages/123456789/Page" --body-markdown "# Updated"
atlassian-write.sh update-wiki-page --page-url "https://example.atlassian.net/wiki/spaces/UM/pages/123456789/Page" --title "Updated title" --body-markdown "# Updated"
```

## Output

JSON with updated page id, title, parent_id, parent_type, space_id, version_number, web_url, labels, conversion_warnings, warnings, and errors.

## Safety

Write operation. Replaces the target page body and creates a new Confluence page version. Does not accept arbitrary HTML or storage XHTML; Markdown is converted through the bounded internal converter. The target must be a page URL, not a folder URL.
