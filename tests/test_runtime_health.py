from __future__ import annotations

import unittest
from datetime import datetime, timezone

from scout_pipeline.runtime_health import evaluate_runtime_health, parse_timestamp
from check_runtime_health import _should_notify


class RuntimeHealthTest(unittest.TestCase):
    def test_parse_timestamp_supports_rfc3339_and_sqlite_style(self) -> None:
        rfc = parse_timestamp("2026-03-25T08:29:24Z")
        sqlite_style = parse_timestamp("2026-03-25 08:29:24")
        self.assertEqual(rfc, datetime(2026, 3, 25, 8, 29, 24, tzinfo=timezone.utc))
        self.assertEqual(sqlite_style, datetime(2026, 3, 25, 8, 29, 24, tzinfo=timezone.utc))

    def test_evaluate_runtime_health_returns_ok(self) -> None:
        now = datetime(2026, 3, 25, 8, 30, 0, tzinfo=timezone.utc)
        provider_status = {
            "data": {
                "latest_scheduler_run": {"time": "2026-03-25T08:29:24Z"},
                "sources": {"failed": 1, "slow": 0},
            }
        }
        consumer_status = {
            "reports": {"latest_report_date": "2026-03-25"},
            "sync_states": [
                {
                    "provider": "content_service",
                    "state_key": "default",
                    "updated_at": "2026-03-25 08:29:30",
                }
            ],
        }

        result = evaluate_runtime_health(
            provider_status,
            consumer_status,
            now=now,
            max_failed_sources=3,
            max_slow_sources=1,
            max_provider_lag_minutes=180,
            max_checkpoint_lag_minutes=180,
            require_report_today=True,
        )

        self.assertEqual(result["status"], "warn")
        self.assertEqual(len(result["checks"]), 5)
        self.assertEqual(result["provider_recent_failures"], [])
        self.assertEqual(result["provider_recent_slow_sources"], [])

    def test_evaluate_runtime_health_includes_recent_failure_details(self) -> None:
        now = datetime(2026, 3, 25, 8, 30, 0, tzinfo=timezone.utc)
        provider_status = {
            "data": {
                "latest_scheduler_run": {"time": "2026-03-25T08:29:24Z"},
                "sources": {
                    "failed": 2,
                    "recent_failures": [
                        {"name": "jiqizhixin_rss", "last_error": "Invalid RSS feed"},
                        {"name": "36kr_hot_list", "last_error": "503 Service Unavailable"},
                    ],
                    "slow": 1,
                    "recent_slow_sources": [
                        {"name": "36kr_news", "last_duration_ms": 18234},
                    ],
                },
            }
        }
        consumer_status = {
            "reports": {"latest_report_date": "2026-03-25"},
            "sync_states": [
                {
                    "provider": "content_service",
                    "state_key": "default",
                    "updated_at": "2026-03-25 08:29:30",
                }
            ],
        }

        result = evaluate_runtime_health(
            provider_status,
            consumer_status,
            now=now,
            max_failed_sources=3,
            max_slow_sources=1,
            max_provider_lag_minutes=180,
            max_checkpoint_lag_minutes=180,
            require_report_today=False,
        )

        self.assertEqual(result["status"], "warn")
        self.assertEqual(len(result["provider_recent_failures"]), 2)
        self.assertEqual(len(result["provider_recent_slow_sources"]), 1)
        failed_check = next(check for check in result["checks"] if check["name"] == "provider_failed_sources")
        self.assertIn("jiqizhixin_rss", failed_check["message"])
        self.assertIn("36kr_hot_list", failed_check["message"])
        slow_check = next(check for check in result["checks"] if check["name"] == "provider_slow_sources")
        self.assertIn("36kr_news", slow_check["message"])

    def test_evaluate_runtime_health_returns_fail_for_stale_checkpoint(self) -> None:
        now = datetime(2026, 3, 25, 12, 0, 0, tzinfo=timezone.utc)
        provider_status = {
            "data": {
                "latest_scheduler_run": {"time": "2026-03-25T11:50:00Z"},
                "sources": {"failed": 0, "slow": 0},
            }
        }
        consumer_status = {
            "reports": {"latest_report_date": "2026-03-25"},
            "sync_states": [
                {
                    "provider": "content_service",
                    "state_key": "default",
                    "updated_at": "2026-03-25 07:00:00",
                }
            ],
        }

        result = evaluate_runtime_health(
            provider_status,
            consumer_status,
            now=now,
            max_failed_sources=3,
            max_slow_sources=1,
            max_provider_lag_minutes=180,
            max_checkpoint_lag_minutes=60,
            require_report_today=False,
        )

        self.assertEqual(result["status"], "fail")
        self.assertTrue(any(check["name"] == "consumer_checkpoint" and check["status"] == "fail" for check in result["checks"]))

    def test_evaluate_runtime_health_fails_when_slow_sources_exceed_threshold(self) -> None:
        now = datetime(2026, 3, 25, 8, 30, 0, tzinfo=timezone.utc)
        provider_status = {
            "data": {
                "latest_scheduler_run": {"time": "2026-03-25T08:29:24Z"},
                "sources": {
                    "failed": 0,
                    "slow": 2,
                    "recent_slow_sources": [
                        {"name": "36kr_news", "last_duration_ms": 18234},
                        {"name": "tmtpost_agi_column", "last_duration_ms": 16500},
                    ],
                },
            }
        }
        consumer_status = {
            "reports": {"latest_report_date": "2026-03-25"},
            "sync_states": [
                {
                    "provider": "content_service",
                    "state_key": "default",
                    "updated_at": "2026-03-25 08:29:30",
                }
            ],
        }

        result = evaluate_runtime_health(
            provider_status,
            consumer_status,
            now=now,
            max_failed_sources=3,
            max_slow_sources=1,
            max_provider_lag_minutes=180,
            max_checkpoint_lag_minutes=180,
            require_report_today=False,
        )

        self.assertEqual(result["status"], "fail")
        slow_check = next(check for check in result["checks"] if check["name"] == "provider_slow_sources")
        self.assertEqual(slow_check["status"], "fail")

    def test_should_notify_respects_threshold(self) -> None:
        self.assertFalse(_should_notify("ok", "fail"))
        self.assertFalse(_should_notify("warn", "fail"))
        self.assertTrue(_should_notify("fail", "fail"))
        self.assertTrue(_should_notify("warn", "warn"))
        self.assertTrue(_should_notify("fail", "warn"))
        self.assertFalse(_should_notify("ok", "warn"))
        self.assertTrue(_should_notify("ok", "always"))
        self.assertFalse(_should_notify("fail", "none"))


if __name__ == "__main__":
    unittest.main()
