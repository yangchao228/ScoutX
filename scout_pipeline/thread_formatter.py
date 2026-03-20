from __future__ import annotations

import re

from scout_pipeline.models import TweetThread


_WHITESPACE_RE = re.compile(r"[ \t]+")


def normalize_text(text: str) -> str:
    lines = [_WHITESPACE_RE.sub(" ", line).strip() for line in (text or "").replace("\r\n", "\n").split("\n")]
    collapsed: list[str] = []
    previous_blank = False
    for line in lines:
        is_blank = not line
        if is_blank and previous_blank:
            continue
        collapsed.append(line)
        previous_blank = is_blank
    return "\n".join(collapsed).strip()


def split_long_text(text: str, max_length: int) -> list[str]:
    normalized = normalize_text(text)
    if not normalized:
        return []
    if len(normalized) <= max_length:
        return [normalized]

    chunks: list[str] = []
    current = ""
    for word in normalized.split():
        if len(word) > max_length:
            if current:
                chunks.append(current)
                current = ""
            start = 0
            while start < len(word):
                chunks.append(word[start : start + max_length])
                start += max_length
            continue

        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_length:
            current = candidate
            continue
        if current:
            chunks.append(current)
        current = word

    if current:
        chunks.append(current)
    return chunks


def normalize_thread_for_x(thread: TweetThread, max_length: int) -> TweetThread:
    tweets: list[str] = []
    for tweet in thread.tweets:
        tweets.extend(split_long_text(tweet, max_length))
    return TweetThread(tweets=[tweet for tweet in tweets if tweet.strip()])
