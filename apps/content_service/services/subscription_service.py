from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from apps.content_service.schemas.content import ContentDTO
from apps.content_service.schemas.subscription import (
    SubscriptionCreateRequest,
    SubscriptionDTO,
    SubscriptionFiltersDTO,
    SubscriptionRunDTO,
    SubscriptionUpdateRequest,
)
from apps.content_service.storage.content_repository import ContentRepository
from apps.content_service.storage.subscription_repository import SubscriptionRepository


def _parse_published_at(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _content_text(item: ContentDTO) -> str:
    return "\n".join(
        [
            item.title,
            item.summary_text,
            item.body_text or "",
            " ".join(item.tags),
            " ".join(item.sources),
        ]
    ).lower()


@dataclass
class SubscriptionService:
    session: Session

    def list_subscriptions(self) -> list[SubscriptionDTO]:
        return SubscriptionRepository(self.session).list_subscriptions()

    def get_subscription(self, subscription_id: str) -> SubscriptionDTO | None:
        return SubscriptionRepository(self.session).get_subscription(subscription_id)

    def create_subscription(self, request: SubscriptionCreateRequest) -> SubscriptionDTO:
        repo = SubscriptionRepository(self.session)
        return repo.create_subscription(
            name=request.name,
            timezone_name=request.timezone,
            cadence=request.cadence,
            delivery_channel=request.delivery_channel,
            language=request.language,
            filters=request.filters.model_dump(mode="python"),
        )

    def update_subscription(
        self,
        subscription_id: str,
        request: SubscriptionUpdateRequest,
    ) -> SubscriptionDTO | None:
        repo = SubscriptionRepository(self.session)
        changes = request.model_dump(exclude_none=True, mode="python")
        if "timezone" in changes:
            changes["timezone"] = changes.pop("timezone")
        if "filters" in changes:
            changes["filters"] = request.filters.model_dump(mode="python")
        return repo.update_subscription(subscription_id, changes=changes)

    def preview_subscription(self, subscription_id: str) -> SubscriptionRunDTO | None:
        subscription = self.get_subscription(subscription_id)
        if subscription is None:
            return None
        items = self._build_preview_items(subscription.filters)
        return SubscriptionRunDTO(
            run_id="preview",
            subscription_id=subscription.subscription_id,
            status="preview",
            delivered_count=len(items),
            started_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            completed_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            preview=items,
        )

    def run_subscription(self, subscription_id: str) -> SubscriptionRunDTO | None:
        subscription = self.get_subscription(subscription_id)
        if subscription is None:
            return None

        items = self._build_preview_items(subscription.filters)
        repo = SubscriptionRepository(self.session)
        run = repo.create_delivery_run(subscription.subscription_id, status="running")
        completed = repo.complete_delivery_run(
            run.run_id,
            status="simulated",
            delivered_count=len(items),
        )
        last_cursor = items[0].updated_at if items else subscription.last_cursor
        repo.update_subscription(
            subscription.subscription_id,
            changes={
                "last_cursor": last_cursor,
                "last_run_at": datetime.now(timezone.utc),
            },
        )
        completed.preview = items
        return completed

    def _build_preview_items(self, filters: SubscriptionFiltersDTO) -> list[ContentDTO]:
        repo = ContentRepository(self.session)
        published_since = None
        if filters.published_within_hours is not None:
            threshold = datetime.now(timezone.utc) - timedelta(hours=filters.published_within_hours)
            published_since = threshold.isoformat().replace("+00:00", "Z")
        raw_items = repo.list_recent_contents(
            limit=max(filters.max_items or 10, 50),
            published_since=published_since,
        )
        filtered = self.apply_filters(raw_items, filters)
        max_items = filters.max_items or 10
        return filtered[:max_items]

    @staticmethod
    def apply_filters(items: list[ContentDTO], filters: SubscriptionFiltersDTO) -> list[ContentDTO]:
        selected: list[ContentDTO] = []
        source_filter = {value.lower() for value in filters.sources}
        tag_filter = {value.lower() for value in filters.tags}
        allow_keywords = [value.lower() for value in filters.keywords_allow]
        deny_keywords = [value.lower() for value in filters.keywords_deny]
        now = datetime.now(timezone.utc)

        for item in items:
            published_at = _parse_published_at(item.published_at)
            if filters.published_within_hours is not None:
                if published_at is None:
                    continue
                if now - published_at > timedelta(hours=filters.published_within_hours):
                    continue

            item_sources = {value.lower() for value in item.sources}
            if source_filter and not (item_sources & source_filter):
                continue

            item_tags = {value.lower() for value in item.tags}
            if tag_filter and not (item_tags & tag_filter):
                continue

            text = _content_text(item)
            if allow_keywords and not any(keyword in text for keyword in allow_keywords):
                continue
            if deny_keywords and any(keyword in text for keyword in deny_keywords):
                continue

            selected.append(item)

        return selected
