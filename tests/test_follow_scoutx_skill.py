from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "skills" / "follow_scoutx" / "scripts" / "follow_scoutx.py"
SPEC = importlib.util.spec_from_file_location("follow_scoutx_skill", SCRIPT_PATH)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class FollowScoutXSkillTest(unittest.TestCase):
    def test_ensure_local_files_bootstraps_profile_state_and_prompts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"FOLLOW_SCOUTX_HOME": tmpdir}, clear=False):
                MODULE.ensure_local_files()

                self.assertTrue((Path(tmpdir) / "profile.json").exists())
                self.assertTrue((Path(tmpdir) / "state.json").exists())
                self.assertTrue((Path(tmpdir) / "prompts" / "digest_intro.md").exists())

    def test_build_preview_items_filters_by_topics_and_exclusions(self) -> None:
        profile = MODULE.default_profile()
        profile["preferences"]["topics"] = ["agent"]
        profile["preferences"]["keywords_exclude"] = ["融资"]
        profile["preferences"]["max_items"] = 5
        payload = {
            "generated_at": "2026-03-25T10:00:00Z",
            "items": [
                {
                    "content_id": "cnt_1",
                    "title": "OpenAI agent runtime update",
                    "summary_text": "New coding agent workflow",
                    "canonical_url": "https://example.com/1",
                    "sources": ["openai_blog"],
                    "tags": ["agents"],
                },
                {
                    "content_id": "cnt_2",
                    "title": "AI 融资新闻",
                    "summary_text": "Agent 公司完成融资",
                    "canonical_url": "https://example.com/2",
                    "sources": ["news_feed"],
                    "tags": ["agents"],
                },
            ],
        }

        items = MODULE.build_preview_items(profile, payload)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["content_id"], "cnt_1")


if __name__ == "__main__":
    unittest.main()
