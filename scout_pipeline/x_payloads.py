from __future__ import annotations

from typing import Any

from scout_pipeline.models import TweetThread
from scout_pipeline.thread_formatter import normalize_thread_for_x


def build_x_post_payloads(thread: TweetThread, max_post_length: int) -> list[dict[str, Any]]:
    normalized = normalize_thread_for_x(thread, max_post_length)
    posts = normalized.tweets
    if not posts:
        raise RuntimeError("no publishable posts generated")

    payloads: list[dict[str, Any]] = []
    for idx, text in enumerate(posts):
        payload: dict[str, Any] = {"text": text}
        if idx > 0:
            payload["reply"] = {"in_reply_to_tweet_id": "__PREVIOUS_POST_ID__"}
        payloads.append(payload)
    return payloads
