#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import date

from scout_pipeline.models import Item, MediaAsset, TweetThread
from scout_pipeline.publisher import build_publisher
from scout_pipeline.report_store import (
    fetch_reports,
    filter_unpushed_items,
    mark_items_pushed,
    record_publication_result,
)
from scout_pipeline.utils import load_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publish stored ScoutX reports to Typefully/X")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--date", dest="report_date", default=date.today().isoformat())
    parser.add_argument("--limit", type=int, default=0, help="Publish only the first N reports, 0 means all")
    parser.add_argument("--force", action="store_true", help="Ignore push_records dedup and publish again")
    parser.add_argument("--source", default=None, help="Publish only reports from the given source")
    parser.add_argument("--contains", default=None, help="Publish only reports whose title contains this text")
    parser.add_argument("--dry-run", action="store_true", help="Print Typefully payloads without calling the API")
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop the batch on first publish error instead of continuing",
    )
    return parser.parse_args()


def _to_item_thread(report: dict) -> tuple[Item, TweetThread]:
    media = [
        MediaAsset(
            url=str(entry.get("url") or ""),
            media_type=str(entry.get("media_type") or "image"),
            local_path=entry.get("local_path"),
        )
        for entry in report.get("media", [])
        if entry.get("url")
    ]
    item = Item(
        source=str(report.get("source") or "unknown"),
        title=str(report.get("title") or ""),
        url=str(report.get("url") or ""),
        description=str(report.get("description") or ""),
        published_at=report.get("published_at"),
        comments=[str(comment) for comment in report.get("comments", [])],
        media=media,
        raw={"report": report},
    )
    thread = TweetThread(tweets=[str(tweet) for tweet in report.get("thread", []) if str(tweet).strip()])
    if not thread.tweets:
        fallback = f"{item.title}\n{item.url}\n\n{item.description}".strip()
        thread = TweetThread(tweets=[fallback])
    return item, thread


def _extract_publication_metadata(response: dict) -> tuple[str | None, str | None]:
    external_id = str(
        response.get("root_id")
        or response.get("id")
        or response.get("draft_id")
        or ""
    ).strip() or None
    external_url = str(
        response.get("url")
        or response.get("share_url")
        or ""
    ).strip() or None
    return external_id, external_url


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    publisher = build_publisher(config.publisher)
    if not publisher:
        raise SystemExit("publisher is disabled in config")

    reports = fetch_reports(config.storage.sqlite_path, args.report_date)
    if args.source:
        reports = [report for report in reports if str(report.get("source") or "") == args.source]
    if args.contains:
        needle = args.contains.lower()
        reports = [report for report in reports if needle in str(report.get("title") or "").lower()]
    if args.limit > 0:
        reports = reports[: args.limit]

    pairs = [_to_item_thread(report) for report in reports]
    if not args.force:
        pairs, skipped = filter_unpushed_items(
            config.storage.sqlite_path,
            publisher.channel_name,
            pairs,
        )
        if skipped:
            print(f"[publish_reports] skipped already published: {skipped}")

    published = 0
    failed = 0
    for item, thread in pairs:
        try:
            if args.dry_run:
                payload = publisher.build_draft_payload(thread)
                print(
                    json.dumps(
                        {
                            "item": {
                                "source": item.source,
                                "title": item.title,
                                "url": item.url,
                            },
                            "payload": payload,
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            else:
                payload = publisher.build_draft_payload(thread)
                publish_response = publisher.publish(item, thread)
                external_id, external_url = _extract_publication_metadata(publish_response)
                mark_items_pushed(config.storage.sqlite_path, publisher.channel_name, [(item, thread)])
                record_publication_result(
                    config.storage.sqlite_path,
                    publisher.channel_name,
                    item,
                    status=(
                        "draft_created"
                        if config.publisher.provider == "typefully"
                        and config.publisher.publish_mode == "draft"
                        else "published"
                    ),
                    mode=config.publisher.publish_mode,
                    external_id=external_id,
                    external_url=external_url,
                    payload=payload,
                    response=publish_response,
                )
            published += 1
        except Exception as exc:
            failed += 1
            record_publication_result(
                config.storage.sqlite_path,
                publisher.channel_name,
                item,
                status="failed",
                mode=config.publisher.publish_mode,
                last_error=str(exc),
            )
            print(f"[publish_reports][warn] {item.source} {item.url} ({exc})")
            if args.stop_on_error:
                break

    print(
        f"[publish_reports] date={args.report_date} candidates={len(pairs)} "
        f"published={published} failed={failed} dry_run={args.dry_run}"
    )
    return 1 if failed and args.stop_on_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
