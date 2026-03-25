from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from apps.content_service.schemas.content import ContentDTO
from apps.content_service.schemas.subscription import SubscriptionFiltersDTO
from apps.content_service.services.subscription_service import SubscriptionService


def make_item(
    *,
    content_id: str,
    title: str,
    summary_text: str = "",
    published_at: str | None = "2026-03-25T01:00:00Z",
    tags: list[str] | None = None,
    sources: list[str] | None = None,
) -> ContentDTO:
    return ContentDTO(
        content_id=content_id,
        title=title,
        canonical_url=f"https://example.com/{content_id}",
        summary_text=summary_text,
        body_text=None,
        published_at=published_at,
        discovered_at="2026-03-25T01:00:00Z",
        updated_at="2026-03-25T01:00:00Z",
        language="zh-CN",
        authors=[],
        tags=tags or [],
        media=[],
        sources=sources or [],
        source_count=1,
    )


class SubscriptionServiceTest(unittest.TestCase):
    def test_apply_filters_matches_source_tag_and_keywords(self) -> None:
        items = [
            make_item(
                content_id="cnt_1",
                title="OpenAI ships new agent runtime",
                summary_text="Strong coding workflow update",
                tags=["agents", "coding"],
                sources=["openai_blog"],
            ),
            make_item(
                content_id="cnt_2",
                title="Funding news",
                summary_text="General AI company update",
                tags=["finance"],
                sources=["news_feed"],
            ),
        ]
        filters = SubscriptionFiltersDTO(
            sources=["openai_blog"],
            tags=["agents"],
            keywords_allow=["runtime"],
            keywords_deny=["funding"],
        )

        selected = SubscriptionService.apply_filters(items, filters)

        self.assertEqual([item.content_id for item in selected], ["cnt_1"])

    def test_apply_filters_excludes_stale_items_when_time_window_set(self) -> None:
        now = datetime.now(timezone.utc)
        fresh_published_at = (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        items = [
            make_item(content_id="cnt_1", title="Fresh", published_at=fresh_published_at),
            make_item(content_id="cnt_2", title="Missing published_at", published_at=None),
        ]
        filters = SubscriptionFiltersDTO(published_within_hours=24)

        selected = SubscriptionService.apply_filters(items, filters)

        self.assertEqual([item.content_id for item in selected], ["cnt_1"])


if __name__ == "__main__":
    unittest.main()
