from __future__ import annotations

import contextlib
import io
import unittest

from mcp_atlassian.cli import build_parser


class AtlassianCliTest(unittest.TestCase):
    def test_read_wiki_page_does_not_accept_user_id(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            build_parser().parse_args(["read-wiki-page", "--page-id", "123", "--user-id", "fan.bai@example.com"])

    def test_search_wiki_pages_accepts_structured_filters(self) -> None:
        args = build_parser().parse_args(
            [
                "search-wiki-pages",
                "design",
                "system",
                "--search-field",
                "title",
                "--parent-url",
                "https://example.atlassian.net/wiki/spaces/UM/pages/123/Parent",
                "--agent-friendly-only",
                "--match",
                "any",
                "--max-results",
                "20",
            ]
        )

        self.assertEqual(args.text, ["design", "system"])
        self.assertEqual(args.search_field, "title")
        self.assertEqual(args.parent_url, "https://example.atlassian.net/wiki/spaces/UM/pages/123/Parent")
        self.assertTrue(args.agent_friendly_only)
        self.assertEqual(args.max_results, 20)
        self.assertFalse(hasattr(args, "user_id"))

    def test_create_wiki_child_page_accepts_body_markdown(self) -> None:
        args = build_parser().parse_args(
            [
                "create-wiki-child-page",
                "--parent-url",
                "https://example.atlassian.net/wiki/spaces/UM/folder/123",
                "--title",
                "New",
                "--body-markdown",
                "# Body",
            ]
        )

        self.assertEqual(args.command, "create-wiki-child-page")
        self.assertEqual(args.parent_url, "https://example.atlassian.net/wiki/spaces/UM/folder/123")
        self.assertEqual(args.body_markdown, "# Body")

    def test_update_wiki_page_accepts_page_url_and_body_markdown(self) -> None:
        args = build_parser().parse_args(
            [
                "update-wiki-page",
                "--page-url",
                "https://example.atlassian.net/wiki/spaces/UM/pages/123/Page",
                "--title",
                "Updated",
                "--body-markdown",
                "# Updated",
                "--version-message",
                "replace content",
            ]
        )

        self.assertEqual(args.command, "update-wiki-page")
        self.assertEqual(args.page_url, "https://example.atlassian.net/wiki/spaces/UM/pages/123/Page")
        self.assertEqual(args.title, "Updated")
        self.assertEqual(args.body_markdown, "# Updated")
        self.assertEqual(args.version_message, "replace content")


if __name__ == "__main__":
    unittest.main()
