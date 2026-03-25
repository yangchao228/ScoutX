from __future__ import annotations

import unittest
from unittest.mock import patch

from scout_pipeline.notifier import notify_feishu_healthcheck


class NotifierTest(unittest.TestCase):
    def test_notify_feishu_healthcheck_includes_slow_sources_section(self) -> None:
        result = {
            "status": "warn",
            "checked_at": "2026-03-25T08:30:00Z",
            "provider_recent_failures": [],
            "provider_recent_slow_sources": [
                {
                    "name": "36kr_news",
                    "last_duration_ms": 18234,
                    "last_run_at": "2026-03-25T08:29:24Z",
                }
            ],
            "checks": [
                {"name": "provider_slow_sources", "status": "warn", "message": "content-service has 1 slow sources"},
            ],
        }

        with patch("scout_pipeline.notifier._post_feishu_card") as post_card:
            notify_feishu_healthcheck(
                "https://example.com/webhook",
                result,
                content_service_url="http://127.0.0.1:9100/v1/status",
                scoutx_url="http://127.0.0.1:9000/api/runtime-status",
            )

        _, title, elements = post_card.call_args.args
        self.assertEqual(title, "ScoutX 巡检告警")
        self.assertTrue(any("最近慢源" in element["content"] for element in elements if element["tag"] == "markdown"))


if __name__ == "__main__":
    unittest.main()
