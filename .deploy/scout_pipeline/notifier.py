from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Iterable

import requests

from scout_pipeline.config import NotifierConfig
from scout_pipeline.models import Item, TweetThread
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


def notify_feishu_daily(webhook: str, items_with_threads: Iterable[tuple[Item, TweetThread]]) -> None:
    """按“日报模板”聚合推送：一次 run 只推 1 条飞书消息。"""

    items_with_threads = list(items_with_threads)
    if not items_with_threads:
        return

    today = date.today().isoformat()
    grouped: dict[str, list[tuple[Item, TweetThread]]] = defaultdict(list)
    for item, thread in items_with_threads:
        grouped[item.source].append((item, thread))

    elements: list[dict] = []
    total = len(items_with_threads)
    elements.append(
        {
            "tag": "markdown",
            "content": f"**ScoutX 日报（本轮新增）**\n\n- 日期：{today}\n- 本轮新增：{total} 条\n",
        }
    )

    shown = 0
    max_items = 12  # 防止卡片过长
    for source, pairs in grouped.items():
        if shown >= max_items:
            break
        elements.append({"tag": "markdown", "content": f"\n**来源：{source}**"})
        for item, thread in pairs:
            if shown >= max_items:
                break
            desc = _truncate(item.description, 140)
            summary = _truncate("\n\n".join(thread.tweets), 240)
            elements.append(
                {
                    "tag": "markdown",
                    "content": f"**• [{item.title}]({item.url})**\n{desc}\n\n{summary}",
                }
            )
            shown += 1

    if total > shown:
        elements.append({"tag": "markdown", "content": f"\n… 还有 {total - shown} 条已省略"})

    body = {
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": f"ScoutX 日报（新增 {total} 条）"}},
            "elements": elements,
        },
    }

    resp = requests.post(
        webhook,
        json=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict) and data.get("code") not in (0, None):
        raise RuntimeError(f"Feishu webhook error: {data}")

    print(f"[feishu] daily push sent: {total} items")


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
    requests.post(url, data=payload, timeout=20)


def notify(config: NotifierConfig, item: Item, thread: TweetThread) -> None:
    """保留逐条通知（目前用于 Telegram）。

    飞书的“日报聚合推送”由 pipeline 在每次 run 结束后统一触发。
    """

    if config.telegram_bot_token_env and config.telegram_chat_id:
        token = require_env(config.telegram_bot_token_env)
        notify_telegram(token, config.telegram_chat_id, item, thread)
