from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

from apps.content_service.services.status_service import StatusService
from apps.content_service.storage.source_snapshot_repository import SourceSnapshotSummary


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
    def __init__(
        self,
        *,
        name,
        source_type,
        schedule="0 * * * *",
        config_json=None,
        last_run_at=None,
        last_success_at=None,
        last_status=None,
        last_error=None,
        last_duration_ms=None,
        consecutive_failures=0,
    ):
        self.name = name
        self.source_type = source_type
        self.schedule = schedule
        self.config_json = config_json or {}
        self.last_run_at = last_run_at
        self.last_success_at = last_success_at
        self.last_status = last_status
        self.last_error = last_error
        self.last_duration_ms = last_duration_ms
        self.consecutive_failures = consecutive_failures


class _FakeSession:
    def __init__(self, results):
        self._results = list(results)

    def execute(self, _stmt):
        return self._results.pop(0)


class StatusServiceTest(unittest.TestCase):
    def test_get_status_builds_summary(self) -> None:
        current_time = datetime.now(timezone.utc)
        session = _FakeSession(
            [
                _FakeResult([139]),
                _FakeResult([datetime(2026, 3, 25, 7, 23, 37, tzinfo=timezone.utc)]),
                _FakeResult(
                    rows=[
                        _FakeSource(
                            name="36kr_news",
                            source_type="rss",
                            schedule="0 */4 * * *",
                            last_status="failed",
                            last_duration_ms=18234,
                            last_error="timeout",
                            last_success_at=current_time - timedelta(hours=20),
                            consecutive_failures=3,
                        ),
                        _FakeSource(
                            name="fresh_source",
                            source_type="json_feed",
                            schedule="0 */4 * * *",
                            last_status="success",
                            last_success_at=current_time - timedelta(hours=1),
                        ),
                    ]
                ),
                _FakeResult(
                    rows=[
                        _FakeSource(
                            name="36kr_news",
                            source_type="rss",
                            last_status="failed",
                            last_error="timeout",
                            last_success_at=current_time - timedelta(hours=20),
                            consecutive_failures=3,
                        )
                    ]
                ),
            ]
        )
        with patch("apps.content_service.services.status_service.load_settings") as load_settings, patch(
            "apps.content_service.services.status_service.RuntimeStateRepository.load_latest_scheduler_run"
        ) as load_latest_scheduler_run, patch(
            "apps.content_service.services.status_service.SourceSnapshotRepository.list_latest_snapshots_by_source_names"
        ) as list_latest_snapshots:
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
            list_latest_snapshots.return_value = {
                "36kr_news": SourceSnapshotSummary(
                    source_name="36kr_news",
                    fetched_at=current_time - timedelta(minutes=15),
                    fetched_from_url="https://cdn.jsdelivr.net/example/feed.json",
                    item_count=18,
                ),
                "fresh_source": SourceSnapshotSummary(
                    source_name="fresh_source",
                    fetched_at=current_time - timedelta(minutes=10),
                    fetched_from_url="https://cdn.jsdelivr.net/example/empty-feed.json",
                    item_count=0,
                )
            }
            status = StatusService(session).get_status()

        self.assertEqual(status.contents.total, 139)
        self.assertEqual(status.sources.total, 2)
        self.assertEqual(status.sources.success, 1)
        self.assertEqual(status.sources.failed, 1)
        self.assertEqual(status.sources.slow, 1)
        self.assertEqual(status.sources.stale, 1)
        self.assertEqual(status.sources.empty, 1)
        self.assertEqual(len(status.sources.recent_failures), 1)
        self.assertEqual(status.sources.recent_failures[0].name, "36kr_news")
        self.assertEqual(status.sources.recent_failures[0].consecutive_failures, 3)
        self.assertTrue(status.sources.recent_failures[0].snapshot.has_snapshot)
        self.assertEqual(
            status.sources.recent_failures[0].snapshot.snapshot_fetched_from_url,
            "https://cdn.jsdelivr.net/example/feed.json",
        )
        self.assertEqual(status.sources.recent_failures[0].snapshot.snapshot_item_count, 18)
        self.assertEqual(len(status.sources.recent_slow_sources), 1)
        self.assertEqual(status.sources.recent_slow_sources[0].last_duration_ms, 18234)
        self.assertEqual(len(status.sources.recent_stale_sources), 1)
        self.assertEqual(status.sources.recent_stale_sources[0].name, "36kr_news")
        self.assertTrue(status.sources.recent_stale_sources[0].snapshot.has_snapshot)
        self.assertEqual(len(status.sources.recent_empty_sources), 1)
        self.assertEqual(status.sources.recent_empty_sources[0].name, "fresh_source")
        self.assertTrue(status.sources.recent_empty_sources[0].snapshot.has_snapshot)
        self.assertEqual(status.sources.recent_empty_sources[0].snapshot.snapshot_item_count, 0)
        self.assertIsNotNone(status.latest_scheduler_run)
        self.assertEqual(status.latest_scheduler_run.collected, 30)
        self.assertEqual(status.latest_scheduler_run.created, 2)
        self.assertEqual(status.latest_scheduler_run.slow_sources, 1)

    def test_get_status_marks_missing_snapshot_explicitly(self) -> None:
        current_time = datetime.now(timezone.utc)
        session = _FakeSession(
            [
                _FakeResult([1]),
                _FakeResult([current_time]),
                _FakeResult(
                    rows=[
                        _FakeSource(
                            name="x_feed",
                            source_type="json_feed",
                            last_status="failed",
                            last_error="timeout",
                            last_success_at=current_time - timedelta(hours=12),
                            consecutive_failures=2,
                        )
                    ]
                ),
                _FakeResult(
                    rows=[
                        _FakeSource(
                            name="x_feed",
                            source_type="json_feed",
                            last_status="failed",
                            last_error="timeout",
                            last_success_at=current_time - timedelta(hours=12),
                            consecutive_failures=2,
                        )
                    ]
                ),
            ]
        )
        with patch("apps.content_service.services.status_service.load_settings") as load_settings, patch(
            "apps.content_service.services.status_service.RuntimeStateRepository.load_latest_scheduler_run"
        ) as load_latest_scheduler_run, patch(
            "apps.content_service.services.status_service.SourceSnapshotRepository.list_latest_snapshots_by_source_names"
        ) as list_latest_snapshots:
            load_settings.return_value.app_name = "content-service"
            load_settings.return_value.app_env = "dev"
            load_settings.return_value.slow_source_threshold_ms = 15000
            load_latest_scheduler_run.return_value = None
            list_latest_snapshots.return_value = {}
            status = StatusService(session).get_status()

        self.assertEqual(len(status.sources.recent_failures), 1)
        self.assertFalse(status.sources.recent_failures[0].snapshot.has_snapshot)
        self.assertIsNone(status.sources.recent_failures[0].snapshot.snapshot_fetched_from_url)
        self.assertEqual(status.sources.empty, 0)
        self.assertEqual(status.sources.recent_empty_sources, [])

    def test_get_status_respects_per_source_slow_threshold_override(self) -> None:
        current_time = datetime.now(timezone.utc)
        session = _FakeSession(
            [
                _FakeResult([2]),
                _FakeResult([current_time]),
                _FakeResult(
                    rows=[
                        _FakeSource(
                            name="tmtpost_agi_column",
                            source_type="rss",
                            config_json={"slow_threshold_ms": 30000},
                            last_status="success",
                            last_run_at=current_time - timedelta(minutes=2),
                            last_success_at=current_time - timedelta(minutes=2),
                            last_duration_ms=26697,
                        ),
                        _FakeSource(
                            name="36kr_news",
                            source_type="rss",
                            last_status="success",
                            last_run_at=current_time - timedelta(minutes=1),
                            last_success_at=current_time - timedelta(minutes=1),
                            last_duration_ms=18234,
                        ),
                    ]
                ),
                _FakeResult(rows=[]),
            ]
        )
        with patch("apps.content_service.services.status_service.load_settings") as load_settings, patch(
            "apps.content_service.services.status_service.RuntimeStateRepository.load_latest_scheduler_run"
        ) as load_latest_scheduler_run, patch(
            "apps.content_service.services.status_service.SourceSnapshotRepository.list_latest_snapshots_by_source_names"
        ) as list_latest_snapshots:
            load_settings.return_value.app_name = "content-service"
            load_settings.return_value.app_env = "dev"
            load_settings.return_value.slow_source_threshold_ms = 15000
            load_latest_scheduler_run.return_value = None
            list_latest_snapshots.return_value = {}
            status = StatusService(session).get_status()

        self.assertEqual(status.sources.slow, 1)
        self.assertEqual(len(status.sources.recent_slow_sources), 1)
        self.assertEqual(status.sources.recent_slow_sources[0].name, "36kr_news")


if __name__ == "__main__":
    unittest.main()
