from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from typing import Any

from scout_pipeline.models import Item, MediaAsset


def _requests_get(*args: Any, **kwargs: Any) -> Any:
    import requests

    return requests.get(*args, **kwargs)


def _is_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class ContentServicePullRequest:
    updated_since: str | None
    published_since: str | None
    source: str | None
    tag: str | None
    limit: int
    max_pages: int
    cursor: str | None
    checkpoint_enabled: bool
    checkpoint_key: str | None


@dataclass(frozen=True)
class ContentServicePullResult:
    items: list[Item]
    next_cursor: str | None
    end_cursor: str | None
    pages_fetched: int


@dataclass(frozen=True)
class ContentServiceClient:
    base_url: str
    api_token: str = ""
    timeout: int = 30

    @classmethod
    def from_env(cls) -> "ContentServiceClient":
        base_url = os.getenv("CONTENT_SERVICE_BASE_URL", "").strip().rstrip("/")
        if not base_url:
            raise RuntimeError("Missing env var: CONTENT_SERVICE_BASE_URL")
        return cls(
            base_url=base_url,
            api_token=os.getenv("CONTENT_SERVICE_API_TOKEN", "").strip(),
            timeout=int(os.getenv("CONTENT_SERVICE_TIMEOUT_SECONDS", "30")),
        )

    def list_contents(
        self,
        *,
        updated_since: str | None = None,
        published_since: str | None = None,
        source: str | None = None,
        tag: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[Item], str | None]:
        params: dict[str, Any] = {"limit": limit}
        if updated_since:
            params["updated_since"] = updated_since
        if published_since:
            params["published_since"] = published_since
        if source:
            params["source"] = source
        if tag:
            params["tag"] = tag
        if cursor:
            params["cursor"] = cursor

        response = _requests_get(
            f"{self.base_url}/v1/contents",
            params=params,
            headers=self._build_headers(),
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data") or {}
        items = [self._map_content_item(row) for row in data.get("items") or []]
        next_cursor = data.get("next_cursor")
        return items, str(next_cursor) if next_cursor else None

    def pull(self, request: ContentServicePullRequest) -> ContentServicePullResult:
        all_items: list[Item] = []
        next_cursor = request.cursor
        end_cursor = request.cursor
        pages_fetched = 0

        while pages_fetched < request.max_pages:
            page_items, page_next_cursor = self.list_contents(
                updated_since=request.updated_since,
                published_since=request.published_since,
                source=request.source,
                tag=request.tag,
                limit=request.limit,
                cursor=next_cursor,
            )
            pages_fetched += 1
            all_items.extend(page_items)
            page_end_cursor = page_next_cursor or _derive_end_cursor(page_items)
            if page_end_cursor:
                end_cursor = page_end_cursor
            if not page_next_cursor:
                next_cursor = None
                break
            next_cursor = page_next_cursor

        return ContentServicePullResult(
            items=all_items,
            next_cursor=next_cursor,
            end_cursor=end_cursor,
            pages_fetched=pages_fetched,
        )

    def _build_headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        return headers

    def _map_content_item(self, payload: dict[str, Any]) -> Item:
        media = [
            MediaAsset(
                url=str(asset.get("url") or "").strip(),
                media_type=str(asset.get("media_type") or "image").strip() or "image",
            )
            for asset in payload.get("media") or []
            if str(asset.get("url") or "").strip()
        ]
        sources = [str(source).strip() for source in payload.get("sources") or [] if str(source).strip()]
        description = str(payload.get("summary_text") or payload.get("body_text") or "").strip()
        return Item(
            source=sources[0] if sources else "content_service",
            title=str(payload.get("title") or "").strip(),
            url=str(payload.get("canonical_url") or "").strip(),
            description=description,
            published_at=self._normalize_optional_text(payload.get("published_at")),
            comments=[],
            media=media,
            raw={
                "content_id": self._normalize_optional_text(payload.get("content_id")),
                "sources": sources,
                "updated_at": self._normalize_optional_text(payload.get("updated_at")),
                "service_payload": payload,
            },
        )

    @staticmethod
    def _normalize_optional_text(value: Any) -> str | None:
        text = str(value).strip() if value is not None else ""
        return text or None


def _derive_end_cursor(items: list[Item]) -> str | None:
    if not items:
        return None
    last = items[-1]
    updated_at = str(last.raw.get("updated_at") or "").strip()
    content_id = str(last.raw.get("content_id") or "").strip()
    if not updated_at or not content_id:
        return None
    return f"{updated_at}|{content_id}"


def build_content_service_pull_request(
    base_url: str,
    *,
    checkpoint_cursor: str | None = None,
) -> ContentServicePullRequest:
    explicit_updated_since = os.getenv("CONTENT_SERVICE_UPDATED_SINCE", "").strip() or None
    explicit_cursor = os.getenv("CONTENT_SERVICE_CURSOR", "").strip() or None
    published_since = os.getenv("CONTENT_SERVICE_PUBLISHED_SINCE", "").strip() or None
    source = os.getenv("CONTENT_SERVICE_SOURCE", "").strip() or None
    tag = os.getenv("CONTENT_SERVICE_TAG", "").strip() or None
    checkpoint_disabled = _is_truthy(os.getenv("CONTENT_SERVICE_CHECKPOINT_DISABLED"))
    checkpoint_enabled = not checkpoint_disabled and explicit_updated_since is None and explicit_cursor is None
    checkpoint_key = None
    if checkpoint_enabled:
        checkpoint_key = os.getenv("CONTENT_SERVICE_CHECKPOINT_KEY", "").strip() or _default_checkpoint_key(
            published_since=published_since,
            source=source,
            tag=tag,
        )
    return ContentServicePullRequest(
        updated_since=explicit_updated_since,
        published_since=published_since,
        source=source,
        tag=tag,
        limit=int(os.getenv("CONTENT_SERVICE_PULL_LIMIT", "50")),
        max_pages=max(1, int(os.getenv("CONTENT_SERVICE_PULL_MAX_PAGES", "10"))),
        cursor=explicit_cursor or (checkpoint_cursor if checkpoint_enabled else None),
        checkpoint_enabled=checkpoint_enabled,
        checkpoint_key=checkpoint_key,
    )


def _default_checkpoint_key(
    *,
    published_since: str | None,
    source: str | None,
    tag: str | None,
) -> str:
    raw = "|".join(
        [
            published_since or "",
            source or "",
            tag or "",
        ]
    )
    digest = hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]
    scope = ":".join(part for part in [source or "all", tag or "all"] if part)
    return f"content_service:{scope}:{digest}"


def collect_content_service_items(
    *,
    checkpoint_cursor: str | None = None,
) -> ContentServicePullResult:
    client = ContentServiceClient.from_env()
    request = build_content_service_pull_request(
        client.base_url,
        checkpoint_cursor=checkpoint_cursor,
    )
    result = client.pull(request)
    return ContentServicePullResult(
        items=result.items,
        next_cursor=result.next_cursor,
        end_cursor=result.end_cursor,
        pages_fetched=result.pages_fetched,
    )
