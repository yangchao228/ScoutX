from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Iterable

import requests
from requests import exceptions as requests_exceptions
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from scout_pipeline.config import NotifierConfig
from scout_pipeline.models import Item, TweetThread
from scout_pipeline.report_store import filter_unpushed_items, mark_items_pushed
from scout_pipeline.utils import require_env


def _truncate(text: str, max_len: int) -> str:
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _format_media_links(item: Item) -> str:
    if not item.media:
        return ""
    return "\n".join([f"- {media.url}" for media in item.media[:5]])


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _filter_recent_items(
    items_with_threads: list[tuple[Item, TweetThread]],
    hours: int = 24,
) -> tuple[list[tuple[Item, TweetThread]], int]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    filtered: list[tuple[Item, TweetThread]] = []
    missing_ts = 0
    for item, thread in items_with_threads:
        published_at = _parse_iso_datetime(item.published_at)
        if not published_at:
            missing_ts += 1
            continue
        if published_at >= cutoff:
            filtered.append((item, thread))
    return filtered, missing_ts


@retry(
    retry=retry_if_exception_type((requests_exceptions.RequestException, RuntimeError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=2, max=10),
)
def _post_feishu_card(webhook: str, title: str, elements: list[dict]) -> None:
    body = {
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": title}},
            "elements": elements,
        },
    }

    resp = requests.post(
        webhook,
        json=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        timeout=(5, 20),
    )
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict) and data.get("code") not in (0, None):
        raise RuntimeError(f"Feishu webhook error: {data}")


def _post_feishu_empty_notice(
    webhook: str,
    *,
    reason: str,
    input_count: int = 0,
    missing_published_at: int = 0,
    dedup_skipped: int = 0,
) -> None:
    today = date.today().isoformat()
    details = [
        f"- 日期：{today}",
        f"- 说明：{reason}",
        f"- 本轮候选：{input_count} 条",
    ]
    if missing_published_at:
        details.append(f"- 缺少发布时间：{missing_published_at} 条")
    if dedup_skipped:
        details.append(f"- 已推送去重跳过：{dedup_skipped} 条")
    _post_feishu_card(
        webhook,
        "ScoutX 日报（无新增）",
        [{"tag": "markdown", "content": "**ScoutX 日报**\n\n" + "\n".join(details)}],
    )


def notify_feishu_daily(
    webhook: str,
    items_with_threads: Iterable[tuple[Item, TweetThread]],
    *,
    sqlite_path: str | None = None,
    dedup_channel: str = "feishu_recent_24h",
) -> None:
    """按“日报模板”聚合推送：仅推最近24小时更新，超长自动分多条。"""

    items_with_threads = list(items_with_threads)
    if not items_with_threads:
        _post_feishu_empty_notice(webhook, reason="当前调度周期没有新的可处理条目。", input_count=0)
        print("[feishu] empty notice sent: no input items")
        return
    recent_pairs, missing_ts = _filter_recent_items(items_with_threads, hours=24)
    if not recent_pairs:
        _post_feishu_empty_notice(
            webhook,
            reason="最近24小时内没有符合推送条件的内容。",
            input_count=len(items_with_threads),
            missing_published_at=missing_ts,
        )
        print(
            f"[feishu] no recent items in last 24h "
            f"(input={len(items_with_threads)}, missing_published_at={missing_ts})"
        )
        return
    dedup_skipped = 0
    if sqlite_path:
        recent_pairs, dedup_skipped = filter_unpushed_items(sqlite_path, dedup_channel, recent_pairs)
        if not recent_pairs:
            _post_feishu_empty_notice(
                webhook,
                reason="最近24小时内容已全部推送过，本次无新增推送。",
                input_count=len(items_with_threads),
                missing_published_at=missing_ts,
                dedup_skipped=dedup_skipped,
            )
            print(
                f"[feishu] no unpushed recent items in last 24h "
                f"(input={len(items_with_threads)}, missing_published_at={missing_ts}, dedup_skipped={dedup_skipped})"
            )
            return

    today = date.today().isoformat()
    grouped: dict[str, list[tuple[Item, TweetThread]]] = defaultdict(list)
    for item, thread in recent_pairs:
        grouped[item.source].append((item, thread))
    flat_pairs: list[tuple[Item, TweetThread]] = []
    for source in sorted(grouped):
        flat_pairs.extend(grouped[source])

    max_items_per_message = 10
    total = len(flat_pairs)
    messages_sent = 0
    for start in range(0, total, max_items_per_message):
        chunk = flat_pairs[start : start + max_items_per_message]
        part = (start // max_items_per_message) + 1
        parts = (total + max_items_per_message - 1) // max_items_per_message
        elements: list[dict] = [
            {
                "tag": "markdown",
                "content": (
                    f"**ScoutX 日报（最近24小时更新）**\n\n"
                    f"- 日期：{today}\n"
                    f"- 最近24小时：{total} 条\n"
                    f"- 分片：第 {part}/{parts} 条消息\n"
                    f"- 本片条目：{len(chunk)} 条"
                    + (
                        f"\n- 未带发布时间已跳过：{missing_ts} 条"
                        if part == 1 and missing_ts
                        else ""
                    )
                ),
            }
        ]
        for item, thread in chunk:
            desc = _truncate(item.description, 140)
            summary = _truncate("\n\n".join(thread.tweets), 240)
            published_at = _parse_iso_datetime(item.published_at)
            published_text = (
                published_at.astimezone().strftime("%Y-%m-%d %H:%M")
                if published_at
                else "unknown"
            )
            elements.append(
                {
                    "tag": "markdown",
                    "content": (
                        f"**[{item.title}]({item.url})**\n"
                        f"- 来源：{item.source}\n"
                        f"- 发布时间：{published_text}\n"
                        f"{desc}\n\n{summary}"
                    ),
                }
            )

        title = f"ScoutX 日报（最近24小时 {total} 条）[{part}/{parts}]"
        _post_feishu_card(webhook, title, elements)
        if sqlite_path:
            mark_items_pushed(sqlite_path, dedup_channel, chunk)
        messages_sent += 1

    print(
        f"[feishu] daily push sent: {total} items in {messages_sent} message(s) "
        f"(missing_published_at={missing_ts}, dedup_skipped={dedup_skipped})"
    )


def notify_telegram(token: str, chat_id: str, item: Item, thread: TweetThread) -> None:
    media_links = _format_media_links(item)
    comments = "\n".join([f"- {comment}" for comment in item.comments[:3]])
    text_parts = [item.title, item.url]
    if media_links:
        text_parts.append("\n素材链接\n" + media_links)
    if comments:
        text_parts.append("\n评论\n" + comments)
    text_parts.append("\n" + "\n\n".join(thread.tweets))
    text = "\n".join(text_parts)

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": False}
    resp = requests.post(url, data=payload, timeout=20)
    resp.raise_for_status()


def notify_feishu(webhook: str, item: Item, thread: TweetThread) -> None:
    """兼容旧调用：单条消息也复用日报接口发送。"""
    notify_feishu_daily(webhook, [(item, thread)])


def notify(config: NotifierConfig, item: Item, thread: TweetThread) -> None:
    """保留逐条通知（目前用于 Telegram）。

    飞书的“日报聚合推送”由 pipeline 在每次 run 结束后统一触发。
    """

    if config.telegram_bot_token_env and config.telegram_chat_id:
        token = require_env(config.telegram_bot_token_env)
        notify_telegram(token, config.telegram_chat_id, item, thread)
