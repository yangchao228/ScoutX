#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import date

from scout_pipeline.report_store import fetch_reports
from scout_pipeline.utils import load_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show publish status for stored ScoutX reports")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--date", dest="report_date", default=date.today().isoformat())
    parser.add_argument("--source", default=None)
    parser.add_argument("--only-failed", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    reports = fetch_reports(config.storage.sqlite_path, args.report_date)
    if args.source:
        reports = [report for report in reports if str(report.get("source") or "") == args.source]

    shown = 0
    for report in reports:
        publications = report.get("publications", [])
        if args.only_failed:
            publications = [pub for pub in publications if str(pub.get("status") or "") == "failed"]
            if not publications:
                continue

        status_text = ", ".join(
            f"{pub.get('channel')}={pub.get('status')}@{pub.get('updated_at')}"
            for pub in publications
        ) or "not_published"
        print(f"{report['source']}\t{report['title']}\t{status_text}")
        for pub in publications:
            if pub.get("last_error"):
                print(f"  error: {pub['last_error']}")
            if pub.get("external_url"):
                print(f"  url: {pub['external_url']}")
        shown += 1

    print(f"\nsummary: date={args.report_date} reports={shown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
