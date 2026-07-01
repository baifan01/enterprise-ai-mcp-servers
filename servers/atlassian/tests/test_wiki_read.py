from __future__ import annotations

import unittest

from mcp_atlassian.client import ApiResult
from mcp_atlassian.errors import AtlassianServiceError
from mcp_atlassian.wiki import WikiService, resolve_page_id


class FakeClient:
    def __init__(self, *, fail_comments: bool = False, fail_user: bool = False) -> None:
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []
        self.fail_comments = fail_comments
        self.fail_user = fail_user

    async def get_json(self, path: str, *, params=None, source_api=None):
        self.calls.append(("GET", path, params))
        if path == "/wiki/api/v2/pages/5781061778":
            return ApiResult("GET", path, 200, PAGE_BODY, source_api or path)
        if path == "/wiki/rest/api/user":
            if self.fail_user:
                raise AtlassianServiceError(type="rest_error", message="user failed")
            return ApiResult(
                "GET",
                path,
                200,
                {"accountId": params["accountId"], "displayName": "Fan Bai"},
                source_api or path,
            )
        if path == "/wiki/api/v2/pages/5781061778/footer-comments":
            if self.fail_comments:
                raise AtlassianServiceError(type="rest_error", message="comments failed")
            return ApiResult(
                "GET",
                path,
                200,
                {
                    "results": [
                        {
                            "id": "c1",
                            "authorId": "712020:comment",
                            "createdAt": "2024-01-01T00:00:00.000Z",
                            "updatedAt": "2024-01-02T00:00:00.000Z",
                            "body": {
                                "storage": {"representation": "storage", "value": "<p>Comment</p>"}
                            },
                        }
                    ]
                },
                source_api or path,
            )
        raise AssertionError(path)


PAGE_BODY = {
    "id": "5781061778",
    "parentId": "5342330881",
    "spaceId": "5022482379",
    "status": "current",
    "title": "DevOps Workshop Nov 2023",
    "createdAt": "2023-11-03T13:01:09.284Z",
    "ownerId": "712020:user",
    "authorId": "712020:user",
    "version": {"number": 6},
    "body": {"storage": {"representation": "storage", "value": "<p>Body</p>"}},
    "_links": {
        "base": "https://ubitricity.atlassian.net/wiki",
        "webui": "/spaces/UM/pages/5781061778/Page",
    },
}


class WikiReadTest(unittest.IsolatedAsyncioTestCase):
    async def test_reads_page_with_storage_body_and_user_enrich(self) -> None:
        client = FakeClient()

        result = await WikiService(client).read_page(page_id="5781061778")

        self.assertEqual(result["id"], "5781061778")
        self.assertEqual(result["parent_id"], "5342330881")
        self.assertEqual(result["space_id"], "5022482379")
        self.assertEqual(result["owner"]["display_name"], "Fan Bai")
        self.assertEqual(result["author"]["display_name"], "Fan Bai")
        self.assertEqual(result["version_number"], 6)
        self.assertEqual(result["body"]["value"], "<p>Body</p>")
        self.assertEqual(result["footer_comments"], [])
        self.assertEqual(result["warnings"], [])
        self.assertEqual(client.calls[0][2], {"body-format": "storage"})
        user_calls = [call for call in client.calls if call[1] == "/wiki/rest/api/user"]
        self.assertEqual(len(user_calls), 1)

    async def test_reads_footer_comments_when_requested(self) -> None:
        client = FakeClient()

        result = await WikiService(client).read_page(
            page_id="5781061778", include_footer_comments=True
        )

        self.assertEqual(result["footer_comments"][0]["id"], "c1")
        self.assertEqual(result["footer_comments"][0]["author"]["display_name"], "Fan Bai")

    async def test_comment_failure_does_not_fail_page_read(self) -> None:
        client = FakeClient(fail_comments=True)

        result = await WikiService(client).read_page(
            page_id="5781061778", include_footer_comments=True
        )

        self.assertEqual(result["footer_comments"], [])
        self.assertEqual(result["warnings"][0]["type"], "footer_comments_failed")

    async def test_user_enrich_failure_is_warning(self) -> None:
        client = FakeClient(fail_user=True)

        result = await WikiService(client).read_page(page_id="5781061778")

        self.assertIsNone(result["owner"]["display_name"])
        self.assertEqual(result["warnings"][0]["type"], "user_enrich_failed")

    def test_page_url_parser_supports_browser_urls(self) -> None:
        page_id = resolve_page_id(
            page_id=None,
            page_url="https://ubitricity.atlassian.net/wiki/spaces/UM/pages/5781061778/Page",
        )

        self.assertEqual(page_id, "5781061778")

    def test_page_url_parser_supports_viewpage_urls(self) -> None:
        page_id = resolve_page_id(
            page_id=None,
            page_url="https://ubitricity.atlassian.net/wiki/pages/viewpage.action?pageId=5781061778",
        )

        self.assertEqual(page_id, "5781061778")


if __name__ == "__main__":
    unittest.main()
