from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from scout_pipeline.collector import collect_json_feed, collect_rss
from scout_pipeline.config import JSONFeedSource, RSSSource


class CollectorTest(unittest.TestCase):
    def test_collect_rss_retries_transient_status_and_succeeds(self) -> None:
        source = RSSSource(type="rss", name="36kr_news", url="http://127.0.0.1:1200/36kr/news")

        first = Mock(status_code=503)
        first.raise_for_status.side_effect = AssertionError("should not raise after retryable status")

        second = Mock(status_code=200, content=b"<rss></rss>", url=str(source.url), headers={"Content-Type": "application/rss+xml"})
        second.raise_for_status.return_value = None

        feed = SimpleNamespace(
            bozo=0,
            entries=[
                SimpleNamespace(
                    title="Retry success",
                    link="https://example.com/retry-success",
                    summary="summary",
                    links=[],
                )
            ],
        )

        with patch("scout_pipeline.collector.requests.get", side_effect=[first, second]) as get_mock, patch(
            "scout_pipeline.collector.feedparser.parse",
            return_value=feed,
        ), patch("scout_pipeline.collector.time.sleep") as sleep_mock:
            items = collect_rss(source)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "Retry success")
        self.assertEqual(get_mock.call_count, 2)
        sleep_mock.assert_called_once()

    def test_collect_rss_surfaces_redirected_html_as_invalid_feed(self) -> None:
        source = RSSSource(type="rss", name="jiqizhixin_rss", url="https://www.jiqizhixin.com/rss")
        response = Mock(
            status_code=200,
            content=b"<html></html>",
            url="https://jiqizhixin.feishu.cn/share/base/form/example",
            headers={"Content-Type": "text/html; charset=utf-8"},
        )
        response.raise_for_status.return_value = None
        feed = SimpleNamespace(bozo=1, entries=[])

        with patch("scout_pipeline.collector.requests.get", return_value=response), patch(
            "scout_pipeline.collector.feedparser.parse",
            return_value=feed,
        ):
            with self.assertRaises(RuntimeError) as ctx:
                collect_rss(source)

        self.assertIn("redirected to non-feed page", str(ctx.exception))

    def test_collect_rss_leaves_placeholder_summary_when_detail_fallback_is_disabled(self) -> None:
        source = RSSSource(type="rss", name="infoq_feed", url="https://www.infoq.cn/feed")

        feed_response = Mock(
            status_code=200,
            content=b"<rss></rss>",
            url=str(source.url),
            headers={"Content-Type": "application/rss+xml"},
        )
        feed_response.raise_for_status.return_value = None

        feed = SimpleNamespace(
            bozo=0,
            entries=[
                SimpleNamespace(
                    title="InfoQ article",
                    link="https://www.infoq.cn/article/example",
                    summary="点击查看原文>",
                    links=[],
                )
            ],
        )

        with patch("scout_pipeline.collector.requests.get", return_value=feed_response) as get_mock, patch(
            "scout_pipeline.collector.feedparser.parse",
            return_value=feed,
        ), patch.dict("os.environ", {}, clear=True):
            items = collect_rss(source)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].description, "点击查看原文>")
        self.assertEqual(get_mock.call_count, 1)

    def test_collect_rss_enriches_placeholder_summary_from_detail_page(self) -> None:
        source = RSSSource(type="rss", name="infoq_feed", url="https://www.infoq.cn/feed")

        feed_response = Mock(
            status_code=200,
            content=b"<rss></rss>",
            url=str(source.url),
            headers={"Content-Type": "application/rss+xml"},
        )
        feed_response.raise_for_status.return_value = None

        detail_response = Mock(
            status_code=200,
            text="""
            <html>
              <head>
                <meta property="og:description" content="这是一段来自详情页的有效摘要，用来替换占位符。" />
              </head>
              <body>
                <article><p>正文第一段。</p><p>正文第二段。</p></article>
              </body>
            </html>
            """,
        )
        detail_response.raise_for_status.return_value = None

        feed = SimpleNamespace(
            bozo=0,
            entries=[
                SimpleNamespace(
                    title="InfoQ article",
                    link="https://www.infoq.cn/article/example",
                    summary="点击查看原文>",
                    links=[],
                )
            ],
        )

        with patch("scout_pipeline.collector.requests.get", side_effect=[feed_response, detail_response]), patch(
            "scout_pipeline.collector.feedparser.parse",
            return_value=feed,
        ), patch.dict("os.environ", {"SCOUTX_DETAIL_FALLBACK_ENABLED": "1"}):
            items = collect_rss(source)

        self.assertEqual(len(items), 1)
        self.assertIn("有效摘要", items[0].description)
        self.assertEqual(items[0].raw.get("detail_fallback"), "article_html")

    def test_collect_json_feed_uses_fallback_url_and_parses_items(self) -> None:
        source = JSONFeedSource(
            type="json_feed",
            name="x_primary_feed",
            url="https://raw.githubusercontent.com/example/feed-x.json",
            fallback_urls=["https://mirror.example.com/feed-x.json"],
            items_path="items",
        )

        success_response = Mock(status_code=200, url="https://mirror.example.com/feed-x.json")
        success_response.raise_for_status.return_value = None
        success_response.json.return_value = {
            "items": [
                {
                    "title": "Agent update",
                    "canonical_url": "https://example.com/a",
                    "summary_text": "Summary from mirror",
                    "published_at": "2026-04-21T08:00:00Z",
                    "image": "https://example.com/a.png",
                }
            ]
        }

        with patch(
            "scout_pipeline.collector._fetch_response",
            side_effect=[RuntimeError("timeout"), success_response],
        ):
            result = collect_json_feed(source)

        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.fetched_from_url, "https://mirror.example.com/feed-x.json")
        self.assertEqual(result.items[0].title, "Agent update")
        self.assertEqual(result.items[0].url, "https://example.com/a")
        self.assertEqual(result.items[0].description, "Summary from mirror")
        self.assertEqual(result.snapshot_payload["item_count"], 1)
        self.assertEqual(result.snapshot_payload["fetched_from_url"], "https://mirror.example.com/feed-x.json")

    def test_collect_json_feed_accepts_top_level_list_payload(self) -> None:
        source = JSONFeedSource(
            type="json_feed",
            name="podcast_feed",
            url="https://example.com/feed-podcasts.json",
            items_path=".",
        )
        response = Mock(status_code=200, url=str(source.url))
        response.raise_for_status.return_value = None
        response.json.return_value = [
            {
                "name": "Podcast episode",
                "link": "https://example.com/podcast-1",
                "description": "Episode summary",
                "date": "2026-04-21T09:00:00Z",
            }
        ]

        with patch("scout_pipeline.collector._fetch_response", return_value=response):
            result = collect_json_feed(source)

        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].title, "Podcast episode")
        self.assertEqual(result.items[0].published_at, "2026-04-21T09:00:00+00:00")

    def test_collect_json_feed_flattens_follow_builders_x_feed(self) -> None:
        source = JSONFeedSource(
            type="json_feed",
            name="follow_builders_x_feed",
            url="https://example.com/feed-x.json",
            items_path="x",
        )
        response = Mock(status_code=200, url=str(source.url))
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "x": [
                {
                    "name": "Swyx",
                    "handle": "swyx",
                    "bio": "Builder bio",
                    "tweets": [
                        {
                            "id": "tweet-1",
                            "text": "The only thing more fun than coding with agents is designing with agents",
                            "createdAt": "2026-04-21T03:42:54.000Z",
                            "url": "https://x.com/swyx/status/tweet-1",
                        }
                    ],
                }
            ]
        }

        with patch("scout_pipeline.collector._fetch_response", return_value=response):
            result = collect_json_feed(source)

        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].url, "https://x.com/swyx/status/tweet-1")
        self.assertEqual(result.items[0].published_at, "2026-04-21T03:42:54+00:00")
        self.assertIn("coding with agents", result.items[0].title)
        self.assertIn("Swyx (@swyx):", result.items[0].description)
        self.assertEqual(result.items[0].raw["json_item"]["author_handle"], "swyx")

    def test_collect_json_feed_accepts_named_top_level_key_and_truncates_long_content(self) -> None:
        source = JSONFeedSource(
            type="json_feed",
            name="follow_good_builders_podcasts_feed",
            url="https://example.com/feed-podcasts.json",
            items_path="podcasts",
        )
        response = Mock(status_code=200, url=str(source.url))
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "podcasts": [
                {
                    "name": "No Priors",
                    "title": "The Agentic Economy",
                    "url": "https://www.youtube.com/watch?v=episode",
                    "publishedAt": "2026-04-09T10:00:00.000Z",
                    "transcript": "word " * 400,
                }
            ]
        }

        with patch("scout_pipeline.collector._fetch_response", return_value=response):
            result = collect_json_feed(source)

        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].published_at, "2026-04-09T10:00:00+00:00")
        self.assertTrue(result.items[0].description.startswith("word word"))
        self.assertLessEqual(len(result.items[0].description), 1200)

    def test_collect_json_feed_parses_textual_month_date(self) -> None:
        source = JSONFeedSource(
            type="json_feed",
            name="follow_good_builders_blogs_feed",
            url="https://example.com/feed-blogs.json",
            items_path="blogs",
        )
        response = Mock(status_code=200, url=str(source.url))
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "blogs": [
                {
                    "title": "Preparing your security program for AI-accelerated offense",
                    "url": "https://claude.com/blog/preparing-your-security-program-for-ai-accelerated-offense",
                    "publishedAt": "Apr 10, 2026",
                    "content": "blog content",
                }
            ]
        }

        with patch("scout_pipeline.collector._fetch_response", return_value=response):
            result = collect_json_feed(source)

        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].published_at, "2026-04-10T00:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
