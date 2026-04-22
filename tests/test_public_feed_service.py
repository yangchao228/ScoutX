from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from apps.content_service.schemas.content import ContentDTO
from apps.content_service.services.public_feed_service import PublicFeedService, _map_feed_item


def make_item(
    *,
    content_id: str,
    title: str,
    published_at: str | None,
    summary_text: str = "summary",
    body_text: str | None = None,
) -> ContentDTO:
    return ContentDTO(
        content_id=content_id,
        title=title,
        canonical_url=f"https://example.com/{content_id}",
        summary_text=summary_text,
        body_text=body_text,
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

    def test_public_feed_removes_placeholder_summary(self) -> None:
        item = make_item(
            content_id="cnt_1",
            title="Placeholder",
            published_at="2026-03-25T01:00:00Z",
            summary_text="点击查看原文>",
        )

        feed_item = _map_feed_item(item)

        self.assertEqual(feed_item.summary_text, "")

    def test_public_feed_falls_back_to_body_text_for_placeholder_summary(self) -> None:
        item = make_item(
            content_id="cnt_1",
            title="Fallback",
            published_at="2026-03-25T01:00:00Z",
            summary_text="阅读全文",
            body_text="正文里有更完整的信息。",
        )

        feed_item = _map_feed_item(item)

        self.assertEqual(feed_item.summary_text, "正文里有更完整的信息。")

    def test_public_feed_truncates_long_summary(self) -> None:
        item = make_item(
            content_id="cnt_1",
            title="Long",
            published_at="2026-03-25T01:00:00Z",
            summary_text="a" * 800,
        )

        feed_item = _map_feed_item(item)

        self.assertEqual(len(feed_item.summary_text), 700)


if __name__ == "__main__":
    unittest.main()
