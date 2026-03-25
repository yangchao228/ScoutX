from __future__ import annotations

import os
import unittest
from unittest.mock import Mock, patch

from scout_pipeline.content_client import (
    ContentServiceClient,
    build_content_service_pull_request,
    collect_content_service_items,
)


class ContentServiceClientTest(unittest.TestCase):
    def test_list_contents_maps_payload_to_items(self) -> None:
        client = ContentServiceClient(base_url="http://127.0.0.1:9100", api_token="token", timeout=5)
        response = Mock()
        response.json.return_value = {
            "data": {
                "items": [
                    {
                        "content_id": "cnt_001",
                        "title": "Example title",
                        "canonical_url": "https://example.com/a",
                        "summary_text": "Example summary",
                        "published_at": "2026-03-24T11:00:00Z",
                        "updated_at": "2026-03-24T11:05:00Z",
                        "sources": ["qbitai_rss", "mirror_feed"],
                        "media": [
                            {
                                "url": "https://example.com/image.jpg",
                                "media_type": "image",
                            }
                        ],
                    }
                ],
                "next_cursor": "cursor_123",
            }
        }
        response.raise_for_status.return_value = None

        with patch("scout_pipeline.content_client._requests_get", return_value=response) as get_mock:
            items, next_cursor = client.list_contents(updated_since="2026-03-24T10:00:00Z", limit=10)

        self.assertEqual(next_cursor, "cursor_123")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].source, "qbitai_rss")
        self.assertEqual(items[0].title, "Example title")
        self.assertEqual(items[0].url, "https://example.com/a")
        self.assertEqual(items[0].description, "Example summary")
        self.assertEqual(items[0].raw["content_id"], "cnt_001")
        self.assertEqual(items[0].raw["sources"], ["qbitai_rss", "mirror_feed"])
        self.assertEqual(len(items[0].media), 1)
        get_mock.assert_called_once()

    def test_collect_content_service_items_reads_env(self) -> None:
        response = Mock()
        response.json.return_value = {"data": {"items": [], "next_cursor": None}}
        response.raise_for_status.return_value = None

        env = {
            "CONTENT_SERVICE_BASE_URL": "http://127.0.0.1:9100",
            "CONTENT_SERVICE_API_TOKEN": "secret-token",
            "CONTENT_SERVICE_TIMEOUT_SECONDS": "15",
            "CONTENT_SERVICE_UPDATED_SINCE": "2026-03-24T10:00:00Z",
            "CONTENT_SERVICE_SOURCE": "qbitai_rss",
            "CONTENT_SERVICE_TAG": "ai",
            "CONTENT_SERVICE_PULL_LIMIT": "25",
            "CONTENT_SERVICE_PULL_MAX_PAGES": "3",
        }
        with patch.dict(os.environ, env, clear=False):
            with patch("scout_pipeline.content_client._requests_get", return_value=response) as get_mock:
                result = collect_content_service_items()

        self.assertEqual(result.items, [])
        self.assertIsNone(result.end_cursor)
        self.assertEqual(result.pages_fetched, 1)
        _, kwargs = get_mock.call_args
        self.assertEqual(kwargs["params"]["updated_since"], "2026-03-24T10:00:00Z")
        self.assertEqual(kwargs["params"]["source"], "qbitai_rss")
        self.assertEqual(kwargs["params"]["tag"], "ai")
        self.assertEqual(kwargs["params"]["limit"], 25)
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer secret-token")

    def test_build_pull_request_uses_checkpoint_when_no_explicit_overrides(self) -> None:
        env = {
            "CONTENT_SERVICE_PULL_LIMIT": "25",
            "CONTENT_SERVICE_SOURCE": "qbitai_rss",
        }
        with patch.dict(os.environ, env, clear=False):
            request = build_content_service_pull_request(
                "http://127.0.0.1:9100",
                checkpoint_cursor="2026-03-24T11:05:00Z|cnt_001",
            )

        self.assertTrue(request.checkpoint_enabled)
        self.assertEqual(request.cursor, "2026-03-24T11:05:00Z|cnt_001")
        self.assertEqual(request.source, "qbitai_rss")
        self.assertIsNotNone(request.checkpoint_key)

    def test_build_pull_request_disables_checkpoint_for_explicit_updated_since(self) -> None:
        env = {
            "CONTENT_SERVICE_UPDATED_SINCE": "2026-03-24T10:00:00Z",
        }
        with patch.dict(os.environ, env, clear=False):
            request = build_content_service_pull_request(
                "http://127.0.0.1:9100",
                checkpoint_cursor="2026-03-24T11:05:00Z|cnt_001",
            )

        self.assertFalse(request.checkpoint_enabled)
        self.assertEqual(request.updated_since, "2026-03-24T10:00:00Z")
        self.assertIsNone(request.checkpoint_key)
        self.assertIsNone(request.cursor)

    def test_pull_follows_pagination_until_complete(self) -> None:
        client = ContentServiceClient(base_url="http://127.0.0.1:9100", timeout=5)
        first = Mock()
        first.json.return_value = {
            "data": {
                "items": [
                    {
                        "content_id": "cnt_001",
                        "title": "First",
                        "canonical_url": "https://example.com/1",
                        "summary_text": "One",
                        "updated_at": "2026-03-24T11:05:00Z",
                        "sources": ["qbitai_rss"],
                        "media": [],
                    }
                ],
                "next_cursor": "2026-03-24T11:05:00Z|cnt_001",
            }
        }
        first.raise_for_status.return_value = None
        second = Mock()
        second.json.return_value = {
            "data": {
                "items": [
                    {
                        "content_id": "cnt_002",
                        "title": "Second",
                        "canonical_url": "https://example.com/2",
                        "summary_text": "Two",
                        "updated_at": "2026-03-24T11:06:00Z",
                        "sources": ["qbitai_rss"],
                        "media": [],
                    }
                ],
                "next_cursor": None,
            }
        }
        second.raise_for_status.return_value = None

        request = build_content_service_pull_request("http://127.0.0.1:9100")
        request = request.__class__(
            updated_since=request.updated_since,
            published_since=request.published_since,
            source=request.source,
            tag=request.tag,
            limit=1,
            max_pages=5,
            cursor=None,
            checkpoint_enabled=request.checkpoint_enabled,
            checkpoint_key=request.checkpoint_key,
        )

        with patch("scout_pipeline.content_client._requests_get", side_effect=[first, second]) as get_mock:
            result = client.pull(request)

        self.assertEqual(len(result.items), 2)
        self.assertEqual(result.items[0].title, "First")
        self.assertEqual(result.items[1].title, "Second")
        self.assertEqual(result.pages_fetched, 2)
        self.assertIsNone(result.next_cursor)
        self.assertEqual(result.end_cursor, "2026-03-24T11:06:00Z|cnt_002")
        self.assertEqual(get_mock.call_count, 2)


if __name__ == "__main__":
    unittest.main()
