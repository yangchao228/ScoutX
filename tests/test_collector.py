from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from scout_pipeline.collector import collect_rss
from scout_pipeline.config import RSSSource


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


if __name__ == "__main__":
    unittest.main()
