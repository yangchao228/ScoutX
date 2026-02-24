from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List

from scout_pipeline.analyst import filter_item
from scout_pipeline.collector import collect_sources
from scout_pipeline.config import AppConfig
from scout_pipeline.creator import create_thread
from scout_pipeline.deduper import Deduper
from scout_pipeline.extractor import normalize_items
from scout_pipeline.media import download_media
from scout_pipeline.models import Item, TweetThread
from scout_pipeline.notifier import notify, notify_feishu_daily
from scout_pipeline.report_store import record_report


AI_STRONG_KEYWORDS = [
    "ai",
    "aigc",
    "agi",
    "llm",
    "gpt",
    "openai",
    "altman",
    "ilya",
    "anthropic",
    "claude",
    "gemini",
    "deepseek",
    "minimax",
    "kimi",
    "qwen",
    "copilot",
    "cursor",
    "mcp",
    "rag",
    "sora",
    "人工智能",
    "大模型",
    "智能体",
    "生成式",
    "机器学习",
    "深度学习",
    "多模态",
    "推理模型",
    "语言模型",
    "机器人",
    "千问",
    "通义",
    "智谱",
    "glm",
    "豆包",
    "文心",
    "混元",
    "奥特曼",
]

AI_CONTEXT_KEYWORDS = [
    "模型",
    "推理",
    "训练",
    "token",
    "tokens",
    "agent",
    "prompt",
    "embedding",
    "transformer",
    "生成",
    "算力",
    "算法",
    "芯片",
    "gpu",
    "npu",
]

FEISHU_PUSH_HOURS = {8, 12, 16, 20}
CN_TZ = timezone(timedelta(hours=8))


def _normalize_text(text: str) -> str:
    return (text or "").lower()


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword.lower() in text for keyword in keywords)


def _count_keyword_hits(text: str, keywords: list[str]) -> int:
    return sum(1 for keyword in keywords if keyword.lower() in text)


def _looks_ai_related(item: Item) -> bool:
    title = _normalize_text(item.title)
    desc = _normalize_text(item.description)
    text = f"{title} {desc}".strip()

    strong_in_title = _contains_any(title, AI_STRONG_KEYWORDS)
    strong_in_text = _contains_any(text, AI_STRONG_KEYWORDS)
    context_title_hits = _count_keyword_hits(title, AI_CONTEXT_KEYWORDS)
    context_hits = _count_keyword_hits(text, AI_CONTEXT_KEYWORDS)

    source = (item.source or "").lower()
    broad_source = source.startswith("36kr_") or source.startswith("infoq")
    ai_focused_source = any(
        key in source for key in ("qbitai", "jiqizhixin", "agi", "infoq")
    )

    if broad_source:
        if strong_in_title:
            return True
        return context_title_hits >= 2

    if strong_in_title:
        return True
    if strong_in_text and context_hits >= 1:
        return True
    if strong_in_text:
        return True
    if ai_focused_source and (context_title_hits >= 1 or context_hits >= 2):
        return True

    return context_hits >= 3


def apply_keyword_filters(items: List[Item], allow: list[str], deny: list[str]) -> List[Item]:
    filtered = []
    for item in items:
        text = _normalize_text(f"{item.title} {item.description}")
        if deny and _contains_any(text, deny):
            continue
        if not _looks_ai_related(item):
            continue
        if allow and not _contains_any(text, allow):
            continue
        filtered.append(item)
    return filtered


def _should_push_feishu_daily(run_started_at: datetime) -> bool:
    local_dt = run_started_at.astimezone(CN_TZ) if run_started_at.tzinfo else run_started_at.replace(tzinfo=CN_TZ)
    return local_dt.hour in FEISHU_PUSH_HOURS and local_dt.minute == 0


def run_once(config: AppConfig) -> None:
    run_started_at = datetime.now(CN_TZ)
    raw_items = collect_sources(config.sources)
    normalized = normalize_items(raw_items)
    filtered = apply_keyword_filters(normalized, config.filters.allow_keywords, config.filters.deny_keywords)

    deduper = Deduper(config.storage.sqlite_path)
    new_items = deduper.filter_new(filtered)

    feishu_batch: list[tuple] = []
    processed = 0

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

        try:
            record_report(config.storage.sqlite_path, item, thread)
        except Exception as exc:
            print(f"[report][warn] failed to save item: {item.source} {item.url} ({exc})")
            continue

        try:
            notify(config.notifier, item, thread)
        except Exception as exc:
            print(f"[notify][warn] per-item notify failed: {item.source} {item.url} ({exc})")

        feishu_batch.append((item, thread))
        processed += 1

    if config.notifier.feishu_webhook and feishu_batch:
        if _should_push_feishu_daily(run_started_at):
            try:
                notify_feishu_daily(
                    str(config.notifier.feishu_webhook),
                    feishu_batch,
                    sqlite_path=config.storage.sqlite_path,
                )
            except Exception as exc:
                print(f"[notify][warn] feishu daily push failed: {exc}")
        else:
            print(
                "[notify] feishu daily push skipped "
                f"(run_started_at={run_started_at.strftime('%Y-%m-%d %H:%M:%S %z')}, "
                f"allowed_hours={sorted(FEISHU_PUSH_HOURS)})"
            )

    print(
        f"[pipeline] collected={len(raw_items)} filtered={len(filtered)} "
        f"new={len(new_items)} processed={processed}"
    )
