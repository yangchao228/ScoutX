from __future__ import annotations

from typing import List

from scout_pipeline.analyst import filter_item
from scout_pipeline.collector import collect_sources
from scout_pipeline.config import AppConfig
from scout_pipeline.creator import create_thread
from scout_pipeline.deduper import Deduper
from scout_pipeline.extractor import normalize_items
from scout_pipeline.media import download_media
from scout_pipeline.models import TweetThread
from scout_pipeline.notifier import notify, notify_feishu_daily
from scout_pipeline.report_store import record_report


def apply_keyword_filters(items: List, allow: list[str], deny: list[str]) -> List:
    filtered = []
    for item in items:
        text = f"{item.title} {item.description}".lower()
        if allow and not any(word.lower() in text for word in allow):
            continue
        if deny and any(word.lower() in text for word in deny):
            continue
        filtered.append(item)
    return filtered


def run_once(config: AppConfig) -> None:
    raw_items = collect_sources(config.sources)
    normalized = normalize_items(raw_items)
    filtered = apply_keyword_filters(normalized, config.filters.allow_keywords, config.filters.deny_keywords)

    deduper = Deduper(config.storage.sqlite_path)
    new_items = deduper.filter_new(filtered)

    feishu_batch: list[tuple] = []

    for item in new_items:
        item = download_media(config.media, item)
        if config.llm.enabled:
            result = filter_item(config.llm, item)
            if not result.passed or result.score < config.filters.min_score:
                continue
            thread = create_thread(config.llm, item)
        else:
            summary = f"{item.title}\n{item.url}\n\n{item.description}".strip()
            thread = TweetThread(tweets=[summary])

        record_report(config.storage.sqlite_path, item, thread)

        # Telegram 仍然逐条推送
        notify(config.notifier, item, thread)

        # 飞书改为本轮聚合后一次性推送
        feishu_batch.append((item, thread))

    if config.notifier.feishu_webhook and feishu_batch:
        notify_feishu_daily(str(config.notifier.feishu_webhook), feishu_batch)
