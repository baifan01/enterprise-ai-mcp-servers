from __future__ import annotations

import unittest

from mcp_atlassian.client import ApiResult
from mcp_atlassian.wiki import AGENT_FRIENDLY_LABEL, WikiService


class FakeSearchClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []
        self.base_url = "https://example.atlassian.net"

    async def get_json(self, path: str, *, params=None, source_api=None):
        self.calls.append(("GET", path, params))
        if path == "/wiki/rest/api/search":
            return ApiResult(
                "GET",
                path,
                200,
                {
                    "results": [
                        {
                            "content": {
                                "id": "child-1",
                                "title": "Child UI",
                                "type": "page",
                                "space": {"id": "space-1"},
                                "_links": {
                                    "base": "https://example.atlassian.net/wiki",
                                    "webui": "/spaces/A/pages/2/Child",
                                },
                            },
                            "excerpt": "UI child",
                            "lastModified": "2024-01-01T00:00:00.000Z",
                        }
                    ]
                },
                source_api or path,
            )
        if path == "/wiki/api/v2/pages/123":
            return ApiResult(
                "GET",
                path,
                200,
                {
                    "id": "123",
                    "spaceId": "space-1",
                    "title": "Parent UI",
                    "body": {
                        "storage": {"representation": "storage", "value": "<p>Parent body</p>"}
                    },
                    "_links": {
                        "base": "https://example.atlassian.net/wiki",
                        "webui": "/spaces/A/pages/123/Parent",
                    },
                },
                source_api or path,
            )
        raise AssertionError(path)


class WikiSearchTest(unittest.IsolatedAsyncioTestCase):
    async def test_builds_structured_cql_with_title_and_label(self) -> None:
        client = FakeSearchClient()

        result = await WikiService(client).search_pages(
            text=["Design", "System"],
            search_field="title",
            agent_friendly_only=True,
            match="any",
            max_results=5,
        )

        cql = client.calls[0][2]["cql"]
        self.assertIn('type = "page"', cql)
        self.assertIn(f'label = "{AGENT_FRIENDLY_LABEL}"', cql)
        self.assertIn('title ~ "Design" OR title ~ "System"', cql)
        self.assertEqual(client.calls[0][2]["limit"], 5)
        self.assertEqual(result["result_count"], 1)

    async def test_parent_search_reads_and_includes_matching_parent(self) -> None:
        client = FakeSearchClient()

        result = await WikiService(client).search_pages(
            text="UI",
            parent_url="https://example.atlassian.net/wiki/spaces/UM/pages/123/Parent",
            max_results=10,
        )

        cql = client.calls[0][2]["cql"]
        self.assertIn("ancestor = 123", cql)
        self.assertEqual(result["results"][0]["id"], "123")
        self.assertEqual(result["results"][1]["id"], "child-1")
        self.assertEqual(
            result["results"][1]["web_url"],
            "https://example.atlassian.net/wiki/spaces/A/pages/2/Child",
        )

    async def test_max_results_is_capped_at_50(self) -> None:
        client = FakeSearchClient()

        await WikiService(client).search_pages(max_results=500)

        self.assertEqual(client.calls[0][2]["limit"], 50)

    async def test_invalid_search_field_fails(self) -> None:
        client = FakeSearchClient()

        with self.assertRaisesRegex(Exception, "search_field"):
            await WikiService(client).search_pages(search_field="space")


if __name__ == "__main__":
    unittest.main()
