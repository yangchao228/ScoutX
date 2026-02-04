from __future__ import annotations

import json
import requests

from scout_pipeline.config import NotifierConfig
from scout_pipeline.models import Item, TweetThread
from scout_pipeline.utils import require_env


def _format_media_links(item: Item) -> str:
    if not item.media:
        return ""
    return "\n".join([f"- {media.url}" for media in item.media[:5]])


def notify_feishu(webhook: str, item: Item, thread: TweetThread) -> None:
    media_links = _format_media_links(item)
    comments = "\n".join([f"- {comment}" for comment in item.comments[:3]])
    elements = [
        {"tag": "markdown", "content": f"[原始链接]({item.url})"},
    ]
    if media_links:
        elements.append({"tag": "markdown", "content": f"**素材链接**\n{media_links}"})
    if comments:
        elements.append({"tag": "markdown", "content": f"**评论**\n{comments}"})
    elements.append({"tag": "markdown", "content": "\n\n".join(thread.tweets)})

    body = {
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": item.title}},
            "elements": elements,
        },
    }
    requests.post(webhook, data=json.dumps(body), headers={"Content-Type": "application/json"}, timeout=20)


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
    if config.feishu_webhook:
        notify_feishu(str(config.feishu_webhook), item, thread)
    if config.telegram_bot_token_env and config.telegram_chat_id:
        token = require_env(config.telegram_bot_token_env)
        notify_telegram(token, config.telegram_chat_id, item, thread)
