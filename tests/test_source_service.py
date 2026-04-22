from __future__ import annotations

from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from apps.content_service.schemas.source import SourceDTO
from apps.content_service.services.source_service import SourceService
from apps.content_service.storage.source_snapshot_repository import SourceSnapshotSummary


class SourceServiceTest(unittest.TestCase):
    def test_list_sources_attaches_snapshot_info(self) -> None:
        items = [
            SourceDTO(
                source_id="src_1",
                name="follow_builders_x_feed",
                type="json_feed",
                enabled=True,
                schedule="0 * * * *",
            ),
            SourceDTO(
                source_id="src_2",
                name="infoq_feed",
                type="rss",
                enabled=True,
                schedule="0 * * * *",
            ),
        ]
        with patch(
            "apps.content_service.services.source_service.SourceRepository.list_sources",
            return_value=items,
        ) as list_sources, patch(
            "apps.content_service.services.source_service.SourceSnapshotRepository.list_latest_snapshots_by_source_names",
            return_value={
                "follow_builders_x_feed": SourceSnapshotSummary(
                    source_name="follow_builders_x_feed",
                    fetched_at=datetime(2026, 4, 21, 9, 0, tzinfo=timezone.utc),
                    fetched_from_url="https://cdn.jsdelivr.net/gh/example/feed-x.json",
                    item_count=12,
                )
            },
        ) as list_snapshots:
            result = SourceService(session=object()).list_sources()

        list_sources.assert_called_once_with(enabled=None, source_type=None)
        list_snapshots.assert_called_once_with(["follow_builders_x_feed", "infoq_feed"])
        self.assertTrue(result[0].snapshot.has_snapshot)
        self.assertEqual(
            result[0].snapshot.snapshot_fetched_from_url,
            "https://cdn.jsdelivr.net/gh/example/feed-x.json",
        )
        self.assertEqual(result[0].snapshot.snapshot_item_count, 12)
        self.assertFalse(result[1].snapshot.has_snapshot)


if __name__ == "__main__":
    unittest.main()
