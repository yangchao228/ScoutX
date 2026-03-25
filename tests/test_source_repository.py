from __future__ import annotations

import unittest
from unittest.mock import Mock

from sqlalchemy.dialects.postgresql import insert

from apps.content_service.storage.models import SourceRecord
from apps.content_service.storage.source_repository import SourceRepository
from apps.content_service.storage.source_ids import compute_source_id


class SourceRepositoryHelpersTest(unittest.TestCase):
    def test_compute_source_id_is_stable(self) -> None:
        self.assertEqual(compute_source_id("jiqizhixin_rss"), compute_source_id("jiqizhixin_rss"))
        self.assertNotEqual(compute_source_id("jiqizhixin_rss"), compute_source_id("infoq_feed"))

    def test_postgres_upsert_targets_type_column_name(self) -> None:
        stmt = insert(SourceRecord).values(
            source_id="src_1",
            name="jiqizhixin_rss",
            type="rss",
            enabled=True,
            schedule="0 * * * *",
            config_json={"type": "rss"},
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[SourceRecord.name],
            set_={"type": "rss"},
        )

        sql = str(stmt)
        self.assertIn("INSERT INTO sources", sql)
        self.assertIn("source_id, name, type, enabled, schedule, config_json", sql)
        self.assertIn("DO UPDATE SET type = ", sql)
        self.assertNotIn("source_type", sql)

    def test_sync_source_configs_disables_missing_sources(self) -> None:
        session = Mock()
        repository = SourceRepository(session)

        repository.sync_source_configs(
            [
                {
                    "type": "rss",
                    "name": "infoq_feed",
                    "url": "https://www.infoq.cn/feed",
                }
            ],
            schedule="0 * * * *",
        )

        self.assertEqual(session.execute.call_count, 2)
        disable_stmt = session.execute.call_args_list[-1].args[0]
        self.assertIn("UPDATE sources SET enabled", str(disable_stmt))
        self.assertIn("sources.name NOT IN", str(disable_stmt))


if __name__ == "__main__":
    unittest.main()
