from __future__ import annotations

import tempfile
import unittest
from datetime import date

from scout_pipeline.models import Item, TweetThread
from scout_pipeline.report_store import (
    fetch_runtime_status,
    fetch_sync_states,
    fetch_reports,
    load_sync_cursor,
    record_publication_result,
    record_report,
    save_sync_cursor,
)


class ReportStoreTest(unittest.TestCase):
    def test_fetch_reports_includes_publication_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            sqlite_path = f"{tmpdir}/test.db"
            report_date = date.today().isoformat()
            item = Item(
                source="infoq_feed",
                title="Test Title",
                url="https://example.com/test",
                description="Test description",
                published_at="2026-03-20T00:00:00+00:00",
            )
            thread = TweetThread(tweets=["tweet one", "tweet two"])

            record_report(sqlite_path, item, thread)
            record_publication_result(
                sqlite_path,
                "publisher:typefully:x",
                item,
                status="draft_created",
                mode="draft",
                external_id="draft-123",
                external_url="https://typefully.com/draft/123",
                payload={"platforms": {"x": {"enabled": True}}},
                response={"id": "draft-123"},
            )

            reports = fetch_reports(sqlite_path, report_date)
            self.assertEqual(len(reports), 1)
            report = reports[0]
            self.assertEqual(report["title"], "Test Title")
            self.assertEqual(report["thread"], ["tweet one", "tweet two"])
            self.assertEqual(len(report["publications"]), 1)
            publication = report["publications"][0]
            self.assertEqual(publication["channel"], "publisher:typefully:x")
            self.assertEqual(publication["status"], "draft_created")
            self.assertEqual(publication["external_url"], "https://typefully.com/draft/123")

    def test_record_publication_result_updates_existing_row(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            sqlite_path = f"{tmpdir}/test.db"
            report_date = date.today().isoformat()
            item = Item(
                source="qbitai",
                title="Another Title",
                url="https://example.com/another",
                description="Another description",
            )
            thread = TweetThread(tweets=["tweet"])

            record_report(sqlite_path, item, thread)
            record_publication_result(
                sqlite_path,
                "publisher:typefully:x",
                item,
                status="failed",
                mode="now",
                last_error="first error",
            )
            record_publication_result(
                sqlite_path,
                "publisher:typefully:x",
                item,
                status="published",
                mode="now",
                external_id="draft-456",
                external_url="https://typefully.com/draft/456",
            )

            reports = fetch_reports(sqlite_path, report_date)
            self.assertEqual(len(reports[0]["publications"]), 1)
            publication = reports[0]["publications"][0]
            self.assertEqual(publication["status"], "published")
            self.assertEqual(publication["external_id"], "draft-456")
            self.assertEqual(publication["last_error"], None)

    def test_sync_cursor_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            sqlite_path = f"{tmpdir}/test.db"
            self.assertIsNone(load_sync_cursor(sqlite_path, "content_service", "default"))

            save_sync_cursor(
                sqlite_path,
                "content_service",
                "default",
                "2026-03-24T11:05:00Z|cnt_001",
            )
            self.assertEqual(
                load_sync_cursor(sqlite_path, "content_service", "default"),
                "2026-03-24T11:05:00Z|cnt_001",
            )

            save_sync_cursor(
                sqlite_path,
                "content_service",
                "default",
                "2026-03-24T12:05:00Z|cnt_002",
            )
            self.assertEqual(
                load_sync_cursor(sqlite_path, "content_service", "default"),
                "2026-03-24T12:05:00Z|cnt_002",
            )

            sync_states = fetch_sync_states(sqlite_path)
            self.assertEqual(len(sync_states), 1)
            self.assertEqual(sync_states[0]["provider"], "content_service")
            self.assertEqual(sync_states[0]["state_key"], "default")

    def test_fetch_runtime_status_includes_reports_publications_and_sync_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            sqlite_path = f"{tmpdir}/test.db"
            item = Item(
                source="infoq_feed",
                title="Runtime Title",
                url="https://example.com/runtime",
                description="Runtime description",
            )
            thread = TweetThread(tweets=["runtime tweet"])

            record_report(sqlite_path, item, thread)
            record_publication_result(
                sqlite_path,
                "publisher:x_official",
                item,
                status="published",
                mode="now",
                external_id="post-1",
                external_url="https://x.com/example/status/1",
            )
            save_sync_cursor(
                sqlite_path,
                "content_service",
                "default",
                "2026-03-24T12:05:00Z|cnt_002",
            )

            status = fetch_runtime_status(sqlite_path)

            self.assertEqual(status["reports"]["total"], 1)
            self.assertEqual(status["reports"]["latest_report_count"], 1)
            self.assertEqual(status["publications"]["total"], 1)
            self.assertEqual(len(status["publications"]["recent"]), 1)
            self.assertEqual(status["publications"]["recent"][0]["status"], "published")
            self.assertEqual(len(status["sync_states"]), 1)
            self.assertEqual(status["sync_states"][0]["cursor"], "2026-03-24T12:05:00Z|cnt_002")


if __name__ == "__main__":
    unittest.main()
