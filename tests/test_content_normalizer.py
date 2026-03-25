from __future__ import annotations

import unittest

from apps.content_service.normalizers.content_normalizer import canonicalize_url, compute_content_id, normalize_content_item
from scout_pipeline.models import Item, MediaAsset


class ContentNormalizerTest(unittest.TestCase):
    def test_canonicalize_url_strips_tracking_query_and_fragment(self) -> None:
        url = "HTTPS://Example.com/path?a=1&utm_source=test&spm=abc#fragment"
        self.assertEqual(canonicalize_url(url), "https://example.com/path?a=1")

    def test_compute_content_id_uses_canonical_url(self) -> None:
        item_a = Item(source="a", title="Same", url="https://example.com/p?utm_source=x", description="")
        item_b = Item(source="b", title="Same", url="https://example.com/p", description="")
        self.assertEqual(compute_content_id(item_a), compute_content_id(item_b))

    def test_normalize_content_item_cleans_html_and_keeps_media(self) -> None:
        item = Item(
            source="feed",
            title="Title",
            url="https://example.com/post?utm_source=test",
            description='<p>Hello <b>World</b><img src="https://example.com/a.jpg" /></p>',
            media=[MediaAsset(url="https://example.com/existing.jpg", media_type="image")],
        )
        normalized = normalize_content_item(item)
        self.assertEqual(normalized.url, "https://example.com/post")
        self.assertEqual(normalized.description, "Hello World")
        self.assertEqual(len(normalized.media), 2)


if __name__ == "__main__":
    unittest.main()
