#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import date

from scout_pipeline.models import Item, MediaAsset, TweetThread
from scout_pipeline.publisher import TypefullyPublisher, build_publisher
from scout_pipeline.report_store import (
    fetch_reports,
    filter_unpushed_items,
    mark_items_pushed,
    record_publication_result,
)
from scout_pipeline.utils import load_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test ScoutX X publishing via Typefully")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--date", dest="report_date", default=date.today().isoformat())
    parser.add_argument("--source", default=None)
    parser.add_argument("--contains", default=None)
    parser.add_argument("--force", action="store_true", help="Ignore push_records dedup when picking a sample")
    parser.add_argument("--live", action="store_true", help="Actually create one draft in Typefully")
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
    tweets = [str(tweet) for tweet in report.get("thread", []) if str(tweet).strip()]
    if not tweets:
        tweets = [f"{item.title}\n{item.url}\n\n{item.description}".strip()]
    return item, TweetThread(tweets=tweets)


def _pick_candidate(
    reports: list[dict],
    publisher,
    sqlite_path: str,
    *,
    force: bool,
) -> tuple[Item, TweetThread] | None:
    pairs = [_to_item_thread(report) for report in reports]
    if force:
        return pairs[0] if pairs else None
    filtered, _skipped = filter_unpushed_items(sqlite_path, publisher.channel_name, pairs)
    return filtered[0] if filtered else None


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    publisher = build_publisher(config.publisher)
    if not publisher:
        raise SystemExit("publisher is disabled in config")
    if not isinstance(publisher, TypefullyPublisher):
        raise SystemExit(f"smoke_publish only supports Typefully currently, got {config.publisher.provider}")

    social_sets = publisher.list_social_sets()
    results = social_sets.get("results", []) if isinstance(social_sets, dict) else []
    matching_social_set = next(
        (entry for entry in results if str(entry.get("id")) == str(config.publisher.social_set_id)),
        None,
    )
    if not matching_social_set:
        raise SystemExit(
            f"publisher.social_set_id={config.publisher.social_set_id} was not found in your Typefully social sets"
        )

    reports = fetch_reports(config.storage.sqlite_path, args.report_date)
    if args.source:
        reports = [report for report in reports if str(report.get("source") or "") == args.source]
    if args.contains:
        needle = args.contains.lower()
        reports = [report for report in reports if needle in str(report.get("title") or "").lower()]

    candidate = _pick_candidate(
        reports,
        publisher,
        config.storage.sqlite_path,
        force=args.force,
    )
    if not candidate:
        raise SystemExit("no candidate report found for smoke test")

    item, thread = candidate
    payload = publisher.build_draft_payload(thread)
    summary = {
        "mode": config.publisher.publish_mode,
        "social_set": {
            "id": matching_social_set.get("id"),
            "name": matching_social_set.get("name"),
            "username": matching_social_set.get("username"),
        },
        "item": {
            "source": item.source,
            "title": item.title,
            "url": item.url,
        },
        "payload": payload,
        "live": args.live,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if not args.live:
        print("[smoke_publish] dry run completed")
        return 0

    response = publisher.publish(item, thread)
    mark_items_pushed(config.storage.sqlite_path, publisher.channel_name, [(item, thread)])
    record_publication_result(
        config.storage.sqlite_path,
        publisher.channel_name,
        item,
        status=(
            "draft_created"
            if config.publisher.publish_mode == "draft"
            else "published"
        ),
        mode=config.publisher.publish_mode,
        external_id=str(response.get("id") or response.get("draft_id") or "") or None,
        external_url=str(response.get("url") or response.get("share_url") or "") or None,
        payload=payload,
        response=response,
    )
    print(
        json.dumps(
            {
                "result": "ok",
                "draft_id": response.get("id") or response.get("draft_id"),
                "url": response.get("url") or response.get("share_url"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
