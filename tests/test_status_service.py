from __future__ import annotations

from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from apps.content_service.services.status_service import StatusService


class _FakeResult:
    def __init__(self, scalar_values=None, rows=None) -> None:
        self._scalar_values = list(scalar_values or [])
        self._rows = list(rows or [])

    def scalar_one(self):
        return self._scalar_values[0]

    def scalar_one_or_none(self):
        return self._scalar_values[0] if self._scalar_values else None

    def scalars(self):
        class _ScalarRows:
            def __init__(self, rows):
                self._rows = rows

            def all(self):
                return self._rows

        return _ScalarRows(self._rows)


class _FakeSource:
    def __init__(self, *, name, source_type, last_run_at=None, last_status=None, last_error=None, last_duration_ms=None):
        self.name = name
        self.source_type = source_type
        self.last_run_at = last_run_at
        self.last_status = last_status
        self.last_error = last_error
        self.last_duration_ms = last_duration_ms


class _FakeSession:
    def __init__(self, results):
        self._results = list(results)

    def execute(self, _stmt):
        return self._results.pop(0)


class StatusServiceTest(unittest.TestCase):
    def test_get_status_builds_summary(self) -> None:
        session = _FakeSession(
            [
                _FakeResult([139]),
                _FakeResult([datetime(2026, 3, 25, 7, 23, 37, tzinfo=timezone.utc)]),
                _FakeResult([10]),
                _FakeResult([6]),
                _FakeResult([4]),
                _FakeResult([1]),
                _FakeResult([0]),
                _FakeResult(rows=[_FakeSource(name="36kr_news", source_type="rss", last_status="failed", last_error="timeout")]),
                _FakeResult(rows=[_FakeSource(name="36kr_news", source_type="rss", last_duration_ms=18234)]),
            ]
        )
        with patch("apps.content_service.services.status_service.load_settings") as load_settings, patch(
            "apps.content_service.services.status_service.RuntimeStateRepository.load_latest_scheduler_run"
        ) as load_latest_scheduler_run:
            load_settings.return_value.app_name = "content-service"
            load_settings.return_value.app_env = "dev"
            load_settings.return_value.slow_source_threshold_ms = 15000
            load_latest_scheduler_run.return_value = {
                "time": "2026-03-25T07:23:37Z",
                "collected": 30,
                "normalized": 30,
                "created": 2,
                "updated": 28,
                "failed_sources": 4,
                "slow_sources": 1,
            }
            status = StatusService(session).get_status()

        self.assertEqual(status.contents.total, 139)
        self.assertEqual(status.sources.total, 10)
        self.assertEqual(status.sources.success, 6)
        self.assertEqual(status.sources.failed, 4)
        self.assertEqual(status.sources.slow, 1)
        self.assertEqual(len(status.sources.recent_failures), 1)
        self.assertEqual(status.sources.recent_failures[0].name, "36kr_news")
        self.assertEqual(len(status.sources.recent_slow_sources), 1)
        self.assertEqual(status.sources.recent_slow_sources[0].last_duration_ms, 18234)
        self.assertIsNotNone(status.latest_scheduler_run)
        self.assertEqual(status.latest_scheduler_run.collected, 30)
        self.assertEqual(status.latest_scheduler_run.created, 2)
        self.assertEqual(status.latest_scheduler_run.slow_sources, 1)


if __name__ == "__main__":
    unittest.main()
