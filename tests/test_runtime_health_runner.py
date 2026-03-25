from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from scout_pipeline.runtime_health_runner import build_parser


class RuntimeHealthRunnerTest(unittest.TestCase):
    def test_build_parser_reads_env_defaults(self) -> None:
        env = {
            "SCOUTX_RUNTIME_HEALTH_CRON": "*/10 * * * *",
            "SCOUTX_RUNTIME_HEALTH_NOTIFY_ON": "warn",
            "SCOUTX_RUNTIME_HEALTH_REQUIRE_REPORT_TODAY": "true",
            "SCOUTX_RUNTIME_HEALTH_MAX_FAILED_SOURCES": "5",
        }
        with patch.dict(os.environ, env, clear=False):
            args = build_parser().parse_args([])

        self.assertEqual(args.cron, "*/10 * * * *")
        self.assertEqual(args.notify_on, "warn")
        self.assertTrue(args.require_report_today)
        self.assertEqual(args.max_failed_sources, 5)


if __name__ == "__main__":
    unittest.main()
