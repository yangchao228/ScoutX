from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from apps.content_service.schemas.content import ContentDTO
from apps.content_service.services.public_feed_service import PublicFeedService


def make_item(
    *,
    content_id: str,
    title: str,
    published_at: str | None,
) -> ContentDTO:
    return ContentDTO(
        content_id=content_id,
        title=title,
        canonical_url=f"https://example.com/{content_id}",
        summary_text="summary",
        body_text=None,
        published_at=published_at,
        discovered_at="2026-03-25T01:00:00Z",
        updated_at="2026-03-25T01:05:00Z",
        language="zh-CN",
        authors=[],
        tags=["agents"],
        media=[],
        sources=["source_a"],
        source_count=1,
    )


class PublicFeedServiceTest(unittest.TestCase):
    def test_filter_items_keeps_recent_items_within_hour_window(self) -> None:
        now = datetime.now(timezone.utc)
        fresh = (now - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
        stale = (now - timedelta(hours=100)).isoformat().replace("+00:00", "Z")
        items = [
            make_item(content_id="cnt_1", title="Fresh", published_at=fresh),
            make_item(content_id="cnt_2", title="Stale", published_at=stale),
            make_item(content_id="cnt_3", title="Missing", published_at=None),
        ]

        selected = PublicFeedService.filter_items(items, hours=72)

        self.assertEqual([item.content_id for item in selected], ["cnt_1"])


if __name__ == "__main__":
    unittest.main()
