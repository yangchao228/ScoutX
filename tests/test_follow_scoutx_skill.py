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

    def test_current_script_path_points_to_loaded_script(self) -> None:
        self.assertEqual(Path(MODULE.current_script_path()), SCRIPT_PATH)

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
                self.assertIn("deliver", command)
                self.assertNotIn("--expect-final", command)

    def test_parser_defaults_to_current_script_path_for_openclaw_cron_commands(self) -> None:
        parser = MODULE.build_parser()
        args = parser.parse_args(["show-openclaw-cron"])
        self.assertEqual(args.script_path, str(SCRIPT_PATH))

        args = parser.parse_args(["install-openclaw-cron"])
        self.assertEqual(args.script_path, str(SCRIPT_PATH))

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
        self.assertNotIn("--expect-final", cron_args)
        self.assertIn(
            "Run `FOLLOW_SCOUTX_FEED_URL=http://192.144.134.94:9100/v1/public/feed python3 skills/follow_scoutx/scripts/follow_scoutx.py deliver`, then send the command output back to the current chat verbatim. Do not rewrite, summarize, or reformat it.",
            cron_args,
        )

    def test_render_digest_uses_full_text_template(self) -> None:
        profile = MODULE.default_profile()
        profile["preferences"]["language"] = "zh-CN"
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

        self.assertIn("Follow ScoutX 摘要", digest)
        self.assertIn("Generated at: 2026-03-30T09:00:00Z", digest)
        self.assertIn("Items: 1", digest)
        self.assertIn("1. OpenAI agent runtime update", digest)
        self.assertIn("New coding agent workflow", digest)
        self.assertIn("Source: openai_blog", digest)
        self.assertIn("Published: 2026-03-30T08:00:00Z", digest)
        self.assertIn("Link: https://example.com/1", digest)

    def test_render_digest_bilingual_uses_bilingual_title(self) -> None:
        profile = MODULE.default_profile()
        profile["preferences"]["language"] = "bilingual"
        digest = MODULE.render_digest(profile, [], "2026-03-30T09:00:00Z")

        self.assertIn("Follow ScoutX Digest / 摘要", digest)
        self.assertIn("Generated at: 2026-03-30T09:00:00Z", digest)
        self.assertIn("No matching items found.", digest)

    def test_render_digest_compresses_long_summary_before_output(self) -> None:
        profile = MODULE.default_profile()
        profile["style"]["length"] = "short"
        long_summary = (
            "第一段：这是背景介绍，说明事情为什么发生，也解释了行业上下文和主要参与方，帮助读者快速理解前因后果。" * 3
            + "\n\n"
            + "第二段：普通描述，没有特别重点，但字数很多很多，用来模拟真实文章中间的大段铺垫和重复叙述。" * 4
            + "\n\n"
            "第三段：数据显示收入增长到20亿美元，因此公司决定扩张。研究发现该模型速度提升6.7倍，同时团队强调这是一次关键升级。\n\n"
            "第四段：更多普通描述，没有特别重点，但会拉长整体字数，模拟资讯稿中常见的细节堆积和重复背景。" * 4
            + "\n\n"
            "最后一段：综上，这件事意味着行业进入新阶段，也说明公司接下来会继续加大投入。"
        )
        digest = MODULE.render_digest(
            profile,
            [
                {
                    "content_id": "cnt_1",
                    "title": "Long summary item",
                    "summary": long_summary,
                    "url": "https://example.com/1",
                    "published_at": "2026-03-30T08:00:00Z",
                    "sources": ["openai_blog"],
                    "tags": ["agent"],
                }
            ],
            "2026-03-30T09:00:00Z",
        )

        self.assertNotIn("第四段：更多普通描述", digest)
        self.assertIn("第三段：数据显示收入增长到20亿美元", digest)
        self.assertIn("最后一段：综上", digest)

    def test_build_prepare_digest_payload_includes_prompts_and_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"FOLLOW_SCOUTX_HOME": tmpdir}, clear=False):
                MODULE.ensure_local_files()
                profile = MODULE.default_profile()
                payload = MODULE.build_prepare_digest_payload(
                    profile,
                    {"generated_at": "2026-03-30T09:00:00Z"},
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
                )

                self.assertEqual(payload["status"], "ok")
                self.assertEqual(payload["stats"]["item_count"], 1)
                self.assertIn("digest_intro", payload["prompts"])
                self.assertIn("item_template", payload["output_contract"])
                self.assertIn("failure_template", payload["output_contract"])
                self.assertEqual(payload["processing"]["mode"], "item_by_item")
                self.assertEqual(payload["processing"]["per_item_input_char_budget"], 700)
                self.assertEqual(payload["processing"]["per_item_timeout_seconds"], 45)
                self.assertEqual(payload["items"][0]["summary_text"], "New coding agent workflow")

    def test_compress_summary_text_keeps_first_key_and_last_sections(self) -> None:
        text = (
            "第一段：这是背景介绍，说明事情为什么发生。\n\n"
            "第二段：普通描述，没有特别重点。\n\n"
            "第三段：数据显示收入增长到20亿美元，因此公司决定扩张。"
            "研究发现该模型速度提升6.7倍。\n\n"
            "第四段：参考资料：https://example.com/source\n\n"
            "最后一段：综上，这件事意味着行业进入新阶段。"
        )

        compressed = MODULE.compress_summary_text(text, char_budget=120)

        self.assertIn("第一段：这是背景介绍", compressed)
        self.assertIn("数据显示收入增长到20亿美元", compressed)
        self.assertIn("最后一段：综上", compressed)
        self.assertNotIn("参考资料", compressed)

    def test_prepare_digest_payload_uses_compressed_summary_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"FOLLOW_SCOUTX_HOME": tmpdir}, clear=False):
                MODULE.ensure_local_files()
                profile = MODULE.default_profile()
                long_summary = (
                    "第一段：这是背景介绍，说明事情为什么发生，也解释了行业上下文和主要参与方，帮助读者快速理解前因后果。\n\n"
                    "第二段：普通描述，没有特别重点，但字数很多很多，用来模拟真实文章中间的大段铺垫和重复叙述。\n\n"
                    "第三段：数据显示收入增长到20亿美元，因此公司决定扩张。研究发现该模型速度提升6.7倍，同时团队强调这是一次关键升级。\n\n"
                    "第四段：更多普通描述，没有特别重点，但会拉长整体字数，模拟资讯稿中常见的细节堆积和重复背景。\n\n"
                    "最后一段：综上，这件事意味着行业进入新阶段，也说明公司接下来会继续加大投入。"
                )
                payload = MODULE.build_prepare_digest_payload(
                    profile,
                    {"generated_at": "2026-03-30T09:00:00Z"},
                    [
                        {
                            "content_id": "cnt_1",
                            "title": "OpenAI agent runtime update",
                            "summary": long_summary,
                            "url": "https://example.com/1",
                            "published_at": "2026-03-30T08:00:00Z",
                            "sources": ["openai_blog"],
                            "tags": ["agent"],
                        }
                    ],
                )
                compressed = MODULE.compress_summary_text(long_summary, char_budget=120)

                self.assertLess(len(compressed), len(long_summary))
                self.assertIn("第一段", compressed)
                self.assertIn("最后一段", compressed)
                self.assertEqual(
                    payload["items"][0]["summary_text"],
                    MODULE.compress_summary_text(
                        long_summary,
                        char_budget=payload["processing"]["per_item_input_char_budget"],
                    ),
                )

    def test_prepare_digest_payload_uses_style_budgets_and_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"FOLLOW_SCOUTX_HOME": tmpdir}, clear=False):
                MODULE.ensure_local_files()
                profile = MODULE.default_profile()
                profile["style"]["length"] = "medium"
                payload = MODULE.build_prepare_digest_payload(
                    profile,
                    {"generated_at": "2026-03-30T09:00:00Z"},
                    [
                        {
                            "content_id": "cnt_1",
                            "title": "OpenAI agent runtime update",
                            "summary": "第一段：背景。\n\n第二段：因此团队决定推进。\n\n最后一段：综上，值得关注。",
                            "url": "https://example.com/1",
                            "published_at": "2026-03-30T08:00:00Z",
                            "sources": ["openai_blog"],
                            "tags": ["agent"],
                        }
                    ],
                )

                self.assertEqual(payload["processing"]["per_item_input_char_budget"], 900)
                self.assertEqual(payload["processing"]["per_item_timeout_seconds"], 60)
                self.assertIn(
                    "If an item cannot be fully produced within the allowed budget or timeout",
                    "\n".join(payload["output_contract"]["rules"]),
                )


if __name__ == "__main__":
    unittest.main()
