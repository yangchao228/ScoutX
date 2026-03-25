from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock

from apps.content_service.schemas.public_feed import PublicFeedDTO


@dataclass(frozen=True)
class CachedFeedEntry:
    feed: PublicFeedDTO
    expires_at: datetime


class PublicFeedCache:
    def __init__(self) -> None:
        self._entries: dict[tuple[int, int], CachedFeedEntry] = {}
        self._lock = Lock()

    def get(self, *, limit: int, hours: int) -> PublicFeedDTO | None:
        key = (limit, hours)
        now = datetime.now(timezone.utc)
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if entry.expires_at <= now:
                self._entries.pop(key, None)
                return None
            return entry.feed

    def set(self, *, limit: int, hours: int, ttl_seconds: int, feed: PublicFeedDTO) -> PublicFeedDTO:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=max(ttl_seconds, 0))
        key = (limit, hours)
        with self._lock:
            self._entries[key] = CachedFeedEntry(feed=feed, expires_at=expires_at)
        return feed

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


public_feed_cache = PublicFeedCache()
