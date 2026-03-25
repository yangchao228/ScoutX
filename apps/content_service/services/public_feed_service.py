from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from apps.content_service.schemas.content import ContentDTO
from apps.content_service.schemas.public_feed import PublicFeedDTO, PublicFeedItemDTO, PublicFeedMetaDTO
from apps.content_service.services.public_feed_cache import public_feed_cache
from apps.content_service.settings import ContentServiceSettings
from apps.content_service.storage.content_repository import ContentRepository


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _map_feed_item(item: ContentDTO) -> PublicFeedItemDTO:
    return PublicFeedItemDTO(
        content_id=item.content_id,
        title=item.title,
        summary_text=item.summary_text,
        canonical_url=item.canonical_url,
        published_at=item.published_at,
        updated_at=item.updated_at,
        language=item.language,
        sources=item.sources,
        tags=item.tags,
    )


@dataclass
class PublicFeedService:
    session: Session
    settings: ContentServiceSettings

    def build_feed(self, *, limit: int = 100, hours: int = 72) -> PublicFeedDTO:
        if self.settings.public_feed_cache_ttl_seconds > 0:
            cached = public_feed_cache.get(limit=limit, hours=hours)
            if cached is not None:
                return cached

        repository = ContentRepository(self.session)
        published_since = None
        if hours > 0:
            published_since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat().replace(
                "+00:00",
                "Z",
            )
        items = repository.list_recent_contents(limit=limit, published_since=published_since)
        feed = PublicFeedDTO(
            generated_at=_utcnow_iso(),
            items=[_map_feed_item(item) for item in items],
        )
        if self.settings.public_feed_cache_ttl_seconds > 0:
            return public_feed_cache.set(
                limit=limit,
                hours=hours,
                ttl_seconds=self.settings.public_feed_cache_ttl_seconds,
                feed=feed,
            )
        return feed

    def build_meta(self) -> PublicFeedMetaDTO:
        return PublicFeedMetaDTO(
            generated_at=_utcnow_iso(),
            feed_url=f"{self.settings.public_base_url}/v1/public/feed",
            default_limit=self.settings.public_feed_default_limit,
            default_hours=self.settings.public_feed_default_hours,
            cache_ttl_seconds=self.settings.public_feed_cache_ttl_seconds,
        )

    @staticmethod
    def filter_items(items: list[ContentDTO], *, hours: int = 72) -> list[ContentDTO]:
        if hours <= 0:
            return items
        threshold = datetime.now(timezone.utc) - timedelta(hours=hours)
        selected: list[ContentDTO] = []
        for item in items:
            if not item.published_at:
                continue
            normalized = item.published_at
            if normalized.endswith("Z"):
                normalized = normalized[:-1] + "+00:00"
            published_at = datetime.fromisoformat(normalized)
            if published_at.tzinfo is None:
                published_at = published_at.replace(tzinfo=timezone.utc)
            if published_at >= threshold:
                selected.append(item)
        return selected
