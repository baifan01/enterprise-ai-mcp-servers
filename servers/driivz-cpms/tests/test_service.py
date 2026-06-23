from __future__ import annotations

import unittest
from typing import Any

from mcp_driivz.client import ApiResult


class FakeDriivzClient:
    def __init__(self) -> None:
        self.post_calls: list[dict[str, Any]] = []

    async def __aenter__(self) -> FakeDriivzClient:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None

    async def post_json(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        source_api: str | None = None,
    ) -> ApiResult:
        self.post_calls.append(
            {
                "path": path,
                "params": params,
                "body": body,
                "source_api": source_api,
            }
        )
        return ApiResult(
            method="POST",
            path=path,
            status_code=200,
            source_api=source_api or f"POST {path}",
            body={
                "requestId": "request-1",
                "count": 1,
                "data": [
                    {
                        "id": "skip-dependent-lookups",
                        "identityKey": "suby1100008277",
                        "siteId": None,
                        "evses": [{"id": "DE*UBI*E10043108"}],
                    }
                ],
            },
        )


class DriivzServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_review_site_runtime_by_key_uses_identity_key_for_device_id(self) -> None:
        from mcp_driivz import service

        client = FakeDriivzClient()

        result = await service._review_with_client(
            client,
            "suby1100008277",
            key_type="device_id",
            include_recent_sessions=False,
        )

        self.assertTrue(result["resolved"])
        self.assertEqual(client.post_calls[0]["body"], {"identityKey": "suby1100008277"})

    async def test_review_site_runtime_by_key_uses_evse_ids_for_evse_id(self) -> None:
        from mcp_driivz import service

        client = FakeDriivzClient()

        result = await service._review_with_client(
            client,
            "DE*UBI*E10043108",
            key_type="evse_id",
            include_recent_sessions=False,
        )

        self.assertTrue(result["resolved"])
        self.assertEqual(result["key"], "DE*UBI*E10043108")
        self.assertEqual(result["key_type"], "evse_id")
        self.assertEqual(result["device_id"], "suby1100008277")
        self.assertEqual(client.post_calls[0]["body"], {"evseIds": ["DE*UBI*E10043108"]})


if __name__ == "__main__":
    unittest.main()
