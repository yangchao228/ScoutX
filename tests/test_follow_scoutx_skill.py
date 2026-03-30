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
                self.assertTrue((Path(tmpdir) / "service.json").exists())
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

    def test_build_openclaw_cron_expression_for_daily_and_weekly_profiles(self) -> None:
        daily_profile = MODULE.default_profile()
        daily_profile["schedule"]["frequency"] = "daily"
        daily_profile["schedule"]["time"] = "09:30"
        self.assertEqual(MODULE.build_openclaw_cron_expression(daily_profile), "30 9 * * *")

        weekly_profile = MODULE.default_profile()
        weekly_profile["schedule"]["frequency"] = "weekly"
        weekly_profile["schedule"]["time"] = "08:15"
        weekly_profile["schedule"]["days"] = ["mon", "thu"]
        self.assertEqual(MODULE.build_openclaw_cron_expression(weekly_profile), "15 8 * * 1,4")

    def test_show_openclaw_cron_uses_local_service_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"FOLLOW_SCOUTX_HOME": tmpdir}, clear=False):
                MODULE.ensure_local_files()
                MODULE.save_service_config(
                    {
                        "feed_url": "http://192.144.134.94:9100/v1/public/feed",
                        "meta_url": "http://192.144.134.94:9100/v1/public/meta",
                        "timeout_seconds": 20,
                    }
                )
                profile = MODULE.load_profile()
                command = MODULE.build_openclaw_cron_command(
                    profile,
                    feed_url="http://192.144.134.94:9100/v1/public/feed",
                    script_path="skills/follow_scoutx/scripts/follow_scoutx.py",
                    name="follow-scoutx-daily",
                    agent="main",
                    timeout_seconds=120,
                )
                self.assertIn("openclaw cron add", command)
                self.assertIn("--announce", command)
                self.assertIn("--channel last", command)
                self.assertIn("FOLLOW_SCOUTX_FEED_URL=http://192.144.134.94:9100/v1/public/feed", command)

    def test_placeholder_feed_url_is_rejected_with_operator_message(self) -> None:
        with self.assertRaises(SystemExit) as exc:
            MODULE.ensure_real_feed_url("https://feed.follow-scoutx.example.com/v1/public/feed")

        self.assertIn("operator setup incomplete", str(exc.exception))
        self.assertIn("should not be asked to provide a feed URL", str(exc.exception))

    def test_build_openclaw_cron_args_matches_command_intent(self) -> None:
        profile = MODULE.default_profile()
        cron_args = MODULE.build_openclaw_cron_args(
            profile,
            feed_url="http://192.144.134.94:9100/v1/public/feed",
            script_path="skills/follow_scoutx/scripts/follow_scoutx.py",
            name="follow-scoutx-daily",
            agent="main",
            timeout_seconds=120,
        )
        self.assertEqual(cron_args[:3], ["openclaw", "cron", "add"])
        self.assertIn("--announce", cron_args)
        self.assertIn("--channel", cron_args)
        self.assertIn("last", cron_args)
        self.assertIn(
            "Run `FOLLOW_SCOUTX_FEED_URL=http://192.144.134.94:9100/v1/public/feed python3 skills/follow_scoutx/scripts/follow_scoutx.py deliver` and return the final digest to the current chat.",
            cron_args,
        )

    def test_render_digest_uses_localized_labels_and_markdown_links(self) -> None:
        profile = MODULE.default_profile()
        profile["preferences"]["language"] = "zh-CN"
        profile["preferences"]["topics"] = ["OpenAI", "Agent"]
        digest = MODULE.render_digest(
            profile,
            [
                {
                    "content_id": "cnt_1",
                    "title": "OpenAI agent runtime update",
                    "summary": "New coding agent workflow",
                    "url": "https://example.com/1",
                    "published_at": "2026-03-30T08:00:00Z",
                    "sources": ["openai_blog"],
                    "tags": ["agent"],
                }
            ],
            "2026-03-30T09:00:00Z",
        )

        self.assertIn("# Follow ScoutX 摘要", digest)
        self.assertIn("- 主题: OpenAI, Agent", digest)
        self.assertIn("## 1. [OpenAI agent runtime update](https://example.com/1)", digest)
        self.assertIn("- 查看原文: [link](https://example.com/1)", digest)

    def test_render_digest_bilingual_uses_bilingual_labels(self) -> None:
        profile = MODULE.default_profile()
        profile["preferences"]["language"] = "bilingual"
        digest = MODULE.render_digest(profile, [], "2026-03-30T09:00:00Z")

        self.assertIn("# Follow ScoutX Digest / 摘要", digest)
        self.assertIn("- Generated at / 生成时间: 2026-03-30T09:00:00Z", digest)
        self.assertIn("No matching items found / 本次没有匹配到内容。", digest)


if __name__ == "__main__":
    unittest.main()
