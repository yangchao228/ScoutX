from __future__ import annotations

import unittest

from apps.content_service.schemas.public_feed import PublicFeedDTO
from apps.content_service.services.public_feed_cache import PublicFeedCache


class PublicFeedCacheTest(unittest.TestCase):
    def test_cache_returns_same_feed_before_expiry(self) -> None:
        cache = PublicFeedCache()
        feed = PublicFeedDTO(generated_at="2026-03-25T06:00:00Z", items=[])

        cache.set(limit=100, hours=72, ttl_seconds=300, feed=feed)
        cached = cache.get(limit=100, hours=72)

        self.assertIsNotNone(cached)
        assert cached is not None
        self.assertEqual(cached.generated_at, "2026-03-25T06:00:00Z")


if __name__ == "__main__":
    unittest.main()
