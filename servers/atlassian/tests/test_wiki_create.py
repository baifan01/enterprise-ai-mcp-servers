from __future__ import annotations

import unittest

from mcp_atlassian.client import ApiResult
from mcp_atlassian.wiki import AGENT_FRIENDLY_LABEL, AI_GENERATED_LABEL, WikiService


class FakeCreateClient:
    def __init__(self, *, fail_labels: bool = False) -> None:
        self.calls: list[tuple[str, str, object]] = []
        self.fail_labels = fail_labels

    async def get_json(self, path: str, *, params=None, source_api=None):
        self.calls.append(("GET", path, params))
        if path == "/wiki/api/v2/pages/123":
            return ApiResult(
                "GET",
                path,
                200,
                {
                    "id": "123",
                    "spaceId": "space-1",
                    "parentId": "root-1",
                    "parentType": "page",
                    "title": "Parent",
                    "version": {"number": 1},
                    "_links": {
                        "base": "https://example.atlassian.net/wiki",
                        "webui": "/spaces/A/pages/123/Parent",
                    },
                },
                source_api or path,
            )
        if path == "/wiki/api/v2/pages/789":
            from mcp_atlassian.errors import AtlassianServiceError

            raise AtlassianServiceError(type="rest_error", message="not a page")
        if path == "/wiki/api/v2/folders/789":
            return ApiResult(
                "GET",
                path,
                200,
                {"id": "789", "spaceId": "space-folder", "title": "Folder"},
                source_api or path,
            )
        raise AssertionError(path)

    async def post_json(self, path: str, *, params=None, body=None, source_api=None):
        self.calls.append(("POST", path, body))
        if path == "/wiki/api/v2/pages":
            return ApiResult(
                "POST",
                path,
                200,
                {
                    "id": "456",
                    "spaceId": "space-1",
                    "status": "current",
                    "title": body["title"],
                    "version": {"number": 1},
                    "_links": {
                        "base": "https://example.atlassian.net/wiki",
                        "webui": "/spaces/A/pages/456/New",
                    },
                },
                source_api or path,
            )
        if path == "/wiki/rest/api/content/456/label":
            if self.fail_labels:
                from mcp_atlassian.errors import AtlassianServiceError

                raise AtlassianServiceError(type="rest_error", message="label failed")
            return ApiResult("POST", path, 200, [], source_api or path)
        if path == "/wiki/rest/api/content/123/label":
            return ApiResult("POST", path, 200, [], source_api or path)
        raise AssertionError(path)

    async def put_json(self, path: str, *, params=None, body=None, source_api=None):
        self.calls.append(("PUT", path, body))
        if path == "/wiki/api/v2/pages/123":
            return ApiResult(
                "PUT",
                path,
                200,
                {
                    "id": "123",
                    "spaceId": "space-1",
                    "parentId": "root-1",
                    "parentType": "page",
                    "status": "current",
                    "title": body["title"],
                    "version": {"number": body["version"]["number"]},
                    "_links": {
                        "base": "https://example.atlassian.net/wiki",
                        "webui": "/spaces/A/pages/123/Updated",
                    },
                },
                source_api or path,
            )
        raise AssertionError(path)


class WikiCreateTest(unittest.IsolatedAsyncioTestCase):
    async def test_creates_page_with_ai_notice_and_labels(self) -> None:
        client = FakeCreateClient()

        result = await WikiService(client).create_child_page(
            parent_url="https://example.atlassian.net/wiki/spaces/UM/pages/123/Parent",
            title="New Page",
            body_markdown="# Hello",
            mark_agent_friendly=True,
        )

        create_body = client.calls[1][2]
        label_body = client.calls[2][2]
        self.assertEqual(create_body["spaceId"], "space-1")
        self.assertEqual(create_body["parentId"], "123")
        self.assertIn('ac:name="panel"', create_body["body"]["value"])
        self.assertIn("AI-generated content", create_body["body"]["value"])
        self.assertIn("<h1>Hello</h1>", create_body["body"]["value"])
        self.assertEqual(result["id"], "456")
        self.assertEqual(result["parent_type"], "page")
        self.assertEqual(result["labels"], [AI_GENERATED_LABEL, AGENT_FRIENDLY_LABEL])
        self.assertEqual(
            [item["name"] for item in label_body], [AI_GENERATED_LABEL, AGENT_FRIENDLY_LABEL]
        )

    async def test_folder_parent_falls_back_after_page_lookup(self) -> None:
        client = FakeCreateClient()

        result = await WikiService(client).create_child_page(
            parent_url="https://example.atlassian.net/wiki/spaces/UM/folder/789",
            title="New Page",
            body_markdown="# Hello",
        )

        create_body = client.calls[2][2]
        self.assertEqual(client.calls[0][1], "/wiki/api/v2/pages/789")
        self.assertEqual(client.calls[1][1], "/wiki/api/v2/folders/789")
        self.assertEqual(create_body["spaceId"], "space-folder")
        self.assertEqual(create_body["parentId"], "789")
        self.assertEqual(result["parent_type"], "folder")

    async def test_image_warning_still_creates_page(self) -> None:
        client = FakeCreateClient()

        result = await WikiService(client).create_child_page(
            parent_url="https://example.atlassian.net/wiki/spaces/UM/pages/123/Parent",
            title="New Page",
            body_markdown="![A](a.png)",
        )

        create_body = client.calls[1][2]
        self.assertIn("[Unsupported image]", create_body["body"]["value"])
        self.assertEqual(result["conversion_warnings"][0]["type"], "unsupported_image")

    async def test_label_failure_is_warning_not_rollback(self) -> None:
        client = FakeCreateClient(fail_labels=True)

        result = await WikiService(client).create_child_page(
            parent_url="https://example.atlassian.net/wiki/spaces/UM/pages/123/Parent",
            title="New Page",
            body_markdown="Body",
        )

        self.assertEqual(result["id"], "456")
        self.assertEqual(result["warnings"][0]["type"], "label_write_failed")

    async def test_update_page_uses_current_version_plus_one(self) -> None:
        client = FakeCreateClient()

        result = await WikiService(client).update_page(
            page_url="https://example.atlassian.net/wiki/spaces/UM/pages/123/Parent",
            body_markdown="# Updated",
        )

        update_body = client.calls[1][2]
        label_body = client.calls[2][2]
        self.assertEqual(update_body["version"]["number"], 2)
        self.assertEqual(update_body["title"], "Parent")
        self.assertIn('ac:name="panel"', update_body["body"]["value"])
        self.assertIn("AI-generated content", update_body["body"]["value"])
        self.assertIn("<h1>Updated</h1>", update_body["body"]["value"])
        self.assertEqual(label_body[0]["name"], AI_GENERATED_LABEL)
        self.assertEqual(result["id"], "123")
        self.assertEqual(result["version_number"], 2)

    async def test_update_page_can_replace_title(self) -> None:
        client = FakeCreateClient()

        result = await WikiService(client).update_page(
            page_url="https://example.atlassian.net/wiki/spaces/UM/pages/123/Parent",
            title="Updated Title",
            body_markdown="Body",
            version_message="replace content",
        )

        update_body = client.calls[1][2]
        self.assertEqual(update_body["title"], "Updated Title")
        self.assertEqual(update_body["version"]["message"], "replace content")
        self.assertEqual(result["title"], "Updated Title")

    async def test_update_page_rejects_folder_url(self) -> None:
        client = FakeCreateClient()

        with self.assertRaisesRegex(Exception, "page id"):
            await WikiService(client).update_page(
                page_url="https://example.atlassian.net/wiki/spaces/UM/folder/789",
                body_markdown="Body",
            )


if __name__ == "__main__":
    unittest.main()
