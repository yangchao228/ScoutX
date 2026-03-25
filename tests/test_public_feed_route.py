from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from apps.content_service.api.routes_public_feed import get_public_feed_service
from apps.content_service.main import create_app
from apps.content_service.schemas.public_feed import PublicFeedDTO, PublicFeedItemDTO


class FakePublicFeedService:
    def build_feed(self, *, limit: int = 100, hours: int = 72) -> PublicFeedDTO:
        return PublicFeedDTO(
            generated_at="2026-03-25T06:00:00Z",
            items=[
                PublicFeedItemDTO(
                    content_id="cnt_1",
                    title="Example title",
                    summary_text="Example summary",
                    canonical_url="https://example.com/a",
                    published_at="2026-03-25T05:00:00Z",
                    updated_at="2026-03-25T05:05:00Z",
                    language="zh-CN",
                    sources=["qbitai_rss"],
                    tags=["ai", "agent"],
                )
            ],
        )


class PublicFeedRouteTest(unittest.TestCase):
    def test_get_public_feed_returns_minimal_feed_shape(self) -> None:
        app = create_app()
        app.dependency_overrides[get_public_feed_service] = lambda: FakePublicFeedService()
        client = TestClient(app)

        response = client.get("/v1/public/feed?limit=10&hours=24")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["generated_at"], "2026-03-25T06:00:00Z")
        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0]["content_id"], "cnt_1")
        self.assertEqual(payload["items"][0]["canonical_url"], "https://example.com/a")


if __name__ == "__main__":
    unittest.main()
