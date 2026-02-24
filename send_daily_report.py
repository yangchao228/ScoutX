#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import date

from scout_pipeline.daily_reporter import send_daily_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send ScoutX daily report to Feishu")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--date", dest="report_date", default=date.today().isoformat())
    parser.add_argument("--webhook", default=None, help="Override notifier.feishu_webhook from config")
    parser.add_argument("--web-base-url", default=None, help="Base URL for daily report page")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print(f"[daily] sending report for {args.report_date}")
    ok = send_daily_report(
        config_path=args.config,
        report_date=args.report_date,
        webhook=args.webhook,
        web_base_url=args.web_base_url,
    )
    if ok:
        print("[daily] done")
        return 0
    print("[daily] failed")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
