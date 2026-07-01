from __future__ import annotations

import unittest

from mcp_atlassian.markdown_storage import markdown_to_storage, with_ai_generated_notice


class MarkdownStorageTest(unittest.TestCase):
    def test_converts_basic_document_blocks(self) -> None:
        result = markdown_to_storage(
            "# Title\n\n"
            "A **bold** paragraph with `code`.\n\n"
            "- first\n"
            "- second\n\n"
            "1. one\n"
            "2. two\n\n"
            "| A | B |\n"
            "| --- | --- |\n"
            "| x | y |\n\n"
            "```text\n"
            "<hello>\n"
            "```"
        )

        self.assertIn("<h1>Title</h1>", result.value)
        self.assertIn("<strong>bold</strong>", result.value)
        self.assertIn("<code>code</code>", result.value)
        self.assertIn("<ul><li><p>first</p></li><li><p>second</p></li></ul>", result.value)
        self.assertIn("<ol><li><p>one</p></li><li><p>two</p></li></ol>", result.value)
        self.assertIn("<table><tbody><tr><th>A</th><th>B</th></tr>", result.value)
        self.assertIn("&lt;hello&gt;", result.value)
        self.assertEqual(result.warnings, [])

    def test_image_generates_warning_notification_and_placeholder(self) -> None:
        result = markdown_to_storage("![Architecture](./architecture.png)")

        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(result.warnings[0].type, "unsupported_image")
        self.assertIn('ac:name="warning"', result.value)
        self.assertIn("[Unsupported image]", result.value)
        self.assertIn("./architecture.png", result.value)

    def test_mermaid_is_preserved_as_code_block(self) -> None:
        result = markdown_to_storage("```mermaid\nsequenceDiagram\nA->>B: hi\n```")

        self.assertIn('data-language="mermaid"', result.value)
        self.assertIn("sequenceDiagram", result.value)
        self.assertEqual(result.warnings, [])

    def test_empty_body_returns_empty_paragraph(self) -> None:
        result = markdown_to_storage("  \n\n")

        self.assertEqual(result.value, "<p></p>")
        self.assertEqual(result.warnings, [])

    def test_ai_generated_notice_is_prepended(self) -> None:
        value = with_ai_generated_notice("<p>Body</p>")

        self.assertTrue(value.startswith('<ac:structured-macro ac:name="panel">'))
        self.assertIn("AI-generated content", value)
        self.assertIn("#E9F2FF", value)
        self.assertIn("<p>Body</p>", value)


if __name__ == "__main__":
    unittest.main()
