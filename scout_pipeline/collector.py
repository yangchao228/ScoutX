from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
import re
import time
from typing import Any, List
from urllib.parse import urljoin

import feedparser
import requests
from bs4 import BeautifulSoup

from scout_pipeline.config import HTMLSource, JSONFeedSource, RSSSource
from scout_pipeline.models import Item, MediaAsset

PLACEHOLDER_DESCRIPTION_MARKERS = (
    "点击查看原文",
    "查看原文",
    "阅读全文",
    "read more",
    "continue reading",
)
DETAIL_EXCERPT_CHAR_LIMIT = 1200
JSON_FEED_EXCERPT_CHAR_LIMIT = 1200


@dataclass(frozen=True)
class FetchPolicy:
    connect_timeout: int
    read_timeout: int
    attempts: int
    backoff_seconds: float
    retry_status_codes: tuple[int, ...] = (429, 500, 502, 503, 504)


@dataclass(frozen=True)
class JSONFeedCollectResult:
    items: list[Item]
    fetched_from_url: str
    snapshot_payload: dict[str, Any]


def _extract_entry_published_at(entry: object) -> str | None:
    for attr in ("published_parsed", "updated_parsed", "created_parsed"):
        parsed = getattr(entry, attr, None)
        if not parsed:
            continue
        try:
            ts = calendar.timegm(parsed)
            return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
        except Exception:
            continue
    return None


def _build_headers(*, is_rss: bool) -> dict[str, str]:
    headers = {
        "User-Agent": "Mozilla/5.0 (ScoutX/1.0; +https://github.com/)",
    }
    if is_rss:
        headers["Accept"] = "application/rss+xml,application/atom+xml,application/xml,text/xml,*/*"
    return headers


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def _is_placeholder_description(value: str) -> bool:
    normalized = _clean_text(value)
    if not normalized:
        return True
    compact = normalized.replace(" ", "").lower()
    return any(marker.replace(" ", "").lower() in compact for marker in PLACEHOLDER_DESCRIPTION_MARKERS)


def _detail_fallback_enabled() -> bool:
    return os.getenv("SCOUTX_DETAIL_FALLBACK_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def _extract_meta_description(soup: BeautifulSoup) -> str:
    for attrs in (
        {"property": "og:description"},
        {"name": "description"},
        {"name": "twitter:description"},
    ):
        node = soup.find("meta", attrs=attrs)
        if node is None:
            continue
        content = _clean_text(str(node.get("content") or ""))
        if content and not _is_placeholder_description(content):
            return content
    return ""


def _extract_detail_paragraphs(soup: BeautifulSoup) -> list[str]:
    selectors = (
        "article p",
        "main p",
        ".article p",
        ".article-content p",
        ".article_content p",
        ".post-content p",
        ".content p",
        ".composite-body p",
        ".text p",
        "p",
    )
    for selector in selectors:
        values: list[str] = []
        seen: set[str] = set()
        for node in soup.select(selector):
            text = _clean_text(node.get_text(" ", strip=True))
            if len(text) < 30 or _is_placeholder_description(text):
                continue
            if text in seen:
                continue
            seen.add(text)
            values.append(text)
        if values:
            return values
    return []


def _fetch_detail_description(item: Item) -> str:
    if not item.url:
        return ""
    response = requests.get(
        item.url,
        timeout=(5, 15),
        headers=_build_headers(is_rss=False),
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")
    fragments: list[str] = []

    meta_description = _extract_meta_description(soup)
    if meta_description:
        fragments.append(meta_description)

    for paragraph in _extract_detail_paragraphs(soup):
        if any(paragraph in existing or existing in paragraph for existing in fragments):
            continue
        fragments.append(paragraph)
        if len("\n\n".join(fragments)) >= DETAIL_EXCERPT_CHAR_LIMIT:
            break

    excerpt = "\n\n".join(fragments).strip()
    if len(excerpt) > DETAIL_EXCERPT_CHAR_LIMIT:
        excerpt = excerpt[:DETAIL_EXCERPT_CHAR_LIMIT].rstrip()
    return excerpt


def _maybe_enrich_item_description(item: Item) -> None:
    if not _detail_fallback_enabled():
        return
    if not _is_placeholder_description(item.description):
        return
    if not item.url:
        return
    try:
        detail_description = _fetch_detail_description(item)
    except Exception as exc:
        print(f"[collector][warn] {item.source} detail fallback failed: {exc}")
        return
    if detail_description:
        item.description = detail_description
        item.raw["detail_fallback"] = "article_html"


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    return str(value).strip()


def _truncate_excerpt(value: str, *, limit: int) -> str:
    text = _clean_text(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _parse_json_feed_published_at(value: Any) -> str | None:
    text = _coerce_text(value)
    if not text:
        return None
    if re.fullmatch(r"\d{10}", text):
        return datetime.fromtimestamp(int(text), tz=timezone.utc).isoformat()
    if re.fullmatch(r"\d{13}", text):
        return datetime.fromtimestamp(int(text) / 1000, tz=timezone.utc).isoformat()
    normalized = text.replace("Z", "+00:00") if text.endswith("Z") else text
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        for fmt in ("%b %d, %Y", "%B %d, %Y"):
            try:
                dt = datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
                break
            except ValueError:
                continue
        else:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _resolve_json_items(payload: Any, items_path: str) -> list[dict[str, Any]]:
    target = payload
    normalized_path = (items_path or "").strip()
    if normalized_path and normalized_path not in {".", "/"}:
        for part in normalized_path.split("."):
            key = part.strip()
            if not key:
                continue
            if isinstance(target, dict) and key in target:
                target = target[key]
                continue
            return []
    if isinstance(target, list):
        return [item for item in target if isinstance(item, dict)]
    if isinstance(target, dict):
        for key in ("items", "data", "entries"):
            value = target.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def _first_text(entry: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = entry.get(key)
        text = _coerce_text(value)
        if text:
            return text
    return ""


def _extract_json_media(entry: dict[str, Any]) -> list[MediaAsset]:
    media: list[MediaAsset] = []
    candidates: list[str] = []
    for key in ("image", "image_url", "cover_image", "thumbnail", "thumbnail_url"):
        value = _coerce_text(entry.get(key))
        if value:
            candidates.append(value)
    raw_media = entry.get("media")
    if isinstance(raw_media, list):
        for item in raw_media:
            if isinstance(item, dict):
                value = _first_text(item, "url", "src", "href")
            else:
                value = _coerce_text(item)
            if value:
                candidates.append(value)
    deduped = list(dict.fromkeys(candidates))
    for value in deduped:
        media.append(MediaAsset(url=value, media_type=_guess_media_type(value)))
    return media


def _candidate_urls(source: RSSSource | HTMLSource | JSONFeedSource) -> list[str]:
    if isinstance(source, JSONFeedSource):
        primary = str(source.url)
        fallbacks = [str(url) for url in source.fallback_urls]
        return list(dict.fromkeys([primary, *fallbacks]))
    return [str(source.url)]


def _policy_for_source(source: RSSSource | HTMLSource | JSONFeedSource, *, target_url: str | None = None) -> FetchPolicy:
    name = str(source.name).lower()
    url = (target_url or str(source.url)).lower()
    if isinstance(source, JSONFeedSource):
        if "raw.githubusercontent.com" in url:
            return FetchPolicy(connect_timeout=5, read_timeout=30, attempts=4, backoff_seconds=2.0)
        return FetchPolicy(connect_timeout=5, read_timeout=20, attempts=3, backoff_seconds=1.5)
    is_36kr = name.startswith("36kr_") or "/36kr/" in url or "36kr.com" in url
    if is_36kr:
        return FetchPolicy(connect_timeout=5, read_timeout=45, attempts=3, backoff_seconds=2.0)
    if isinstance(source, RSSSource):
        return FetchPolicy(connect_timeout=5, read_timeout=25, attempts=2, backoff_seconds=1.5)
    return FetchPolicy(connect_timeout=5, read_timeout=20, attempts=2, backoff_seconds=1.5)


def _is_retryable_request_exception(exc: Exception, retry_status_codes: tuple[int, ...]) -> bool:
    if isinstance(exc, (requests.Timeout, requests.ConnectionError)):
        return True
    if isinstance(exc, requests.HTTPError):
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        return int(status_code) in retry_status_codes if status_code is not None else False
    return False


def _fetch_response(
    source: RSSSource | HTMLSource | JSONFeedSource,
    *,
    is_rss: bool,
    target_url: str | None = None,
) -> requests.Response:
    request_url = target_url or str(source.url)
    policy = _policy_for_source(source, target_url=request_url)
    headers = _build_headers(is_rss=is_rss)
    last_exc: Exception | None = None

    for attempt in range(1, policy.attempts + 1):
        try:
            response = requests.get(
                request_url,
                timeout=(policy.connect_timeout, policy.read_timeout),
                headers=headers,
            )
            if response.status_code in policy.retry_status_codes and attempt < policy.attempts:
                print(
                    "[collector][retry] "
                    f"{source.name}: url={request_url} status={response.status_code} attempt={attempt}/{policy.attempts}"
                )
                time.sleep(policy.backoff_seconds * attempt)
                continue
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < policy.attempts and _is_retryable_request_exception(exc, policy.retry_status_codes):
                status_code = getattr(getattr(exc, "response", None), "status_code", None)
                detail = f"status={status_code}" if status_code is not None else exc.__class__.__name__
                print(
                    "[collector][retry] "
                    f"{source.name}: url={request_url} error={detail} attempt={attempt}/{policy.attempts}"
                )
                time.sleep(policy.backoff_seconds * attempt)
                continue
            raise

    if last_exc is not None:
        raise last_exc
    raise RuntimeError(f"Failed to fetch source: {source.name} ({request_url})")


def _raise_invalid_rss_error(source: RSSSource, response: requests.Response) -> None:
    final_url = str(getattr(response, "url", "") or source.url)
    content_type = str((getattr(response, "headers", {}) or {}).get("Content-Type") or "").lower()
    if "feishu.cn" in final_url:
        raise RuntimeError(
            f"RSS endpoint redirected to non-feed page: {source.name} ({final_url})"
        )
    if "html" in content_type:
        raise RuntimeError(
            f"Invalid RSS feed: {source.name} ({source.url}) returned HTML from {final_url}"
        )
    raise RuntimeError(f"Invalid RSS feed: {source.name} ({source.url})")


def collect_rss(source: RSSSource) -> List[Item]:
    response = _fetch_response(source, is_rss=True)
    feed = feedparser.parse(response.content)

    if getattr(feed, "bozo", 0) and not feed.entries:
        _raise_invalid_rss_error(source, response)

    items: List[Item] = []
    for entry in feed.entries:
        title = getattr(entry, "title", "").strip()
        url = getattr(entry, "link", "").strip()
        description = getattr(entry, "summary", "").strip()
        if not description and hasattr(entry, "description"):
            description = str(getattr(entry, "description", "")).strip()
        comments = []
        if hasattr(entry, "comments") and entry.comments:
            comments = [str(entry.comments)]

        media: List[MediaAsset] = []
        for link in getattr(entry, "links", []):
            if link.get("rel") == "enclosure" and link.get("href"):
                media.append(MediaAsset(url=link["href"], media_type=_guess_media_type(link["href"])))

        if not title and not url:
            continue

        item = Item(
            source=source.name,
            title=title,
            url=url,
            description=description,
            published_at=_extract_entry_published_at(entry),
            comments=comments,
            media=media,
            raw={"entry": entry},
        )
        _maybe_enrich_item_description(item)

        items.append(item)
    return items


def _extract_field(soup: BeautifulSoup, selector: str, attr: str | None, multiple: bool) -> str | List[str]:
    nodes = soup.select(selector)
    if not nodes:
        return [] if multiple else ""
    if multiple:
        values: List[str] = []
        for node in nodes:
            if attr:
                values.append(node.get(attr, "").strip())
            else:
                values.append(node.get_text(strip=True))
        return values
    node = nodes[0]
    return node.get(attr, "").strip() if attr else node.get_text(strip=True)


def _guess_media_type(url: str) -> str:
    lower = url.lower()
    if lower.endswith((".mp4", ".webm", ".mov", ".gif")):
        return "video"
    return "image"


def _flatten_follow_builders_x_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for entry in entries:
        tweets = entry.get("tweets")
        if not isinstance(tweets, list):
            continue
        author_name = _first_text(entry, "name")
        author_handle = _first_text(entry, "handle")
        author_bio = _first_text(entry, "bio", "description", "summary")
        author_label = " ".join(part for part in (author_name, f"(@{author_handle})" if author_handle else "") if part).strip()
        for tweet in tweets:
            if not isinstance(tweet, dict):
                continue
            text = _first_text(tweet, "text", "content", "body_text")
            normalized_tweet = dict(tweet)
            if text:
                normalized_tweet.setdefault("title", _truncate_excerpt(text, limit=100))
                normalized_tweet.setdefault("description", f"{author_label}: {text}" if author_label else text)
            if author_name:
                normalized_tweet.setdefault("author_name", author_name)
            if author_handle:
                normalized_tweet.setdefault("author_handle", author_handle)
            if author_bio:
                normalized_tweet.setdefault("author_bio", author_bio)
            if tweet.get("createdAt") and not normalized_tweet.get("published_at"):
                normalized_tweet["published_at"] = tweet.get("createdAt")
            flattened.append(normalized_tweet)
    return flattened


def _normalize_json_feed_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if entries and all(isinstance(entry.get("tweets"), list) for entry in entries):
        return _flatten_follow_builders_x_entries(entries)
    return entries


def _extract_json_description(entry: dict[str, Any]) -> str:
    value = _first_text(
        entry,
        "summary_text",
        "summary",
        "description",
        "content_text",
        "transcript_excerpt",
        "transcript",
        "content",
        "body_text",
    )
    if not value:
        return ""
    return _truncate_excerpt(value, limit=JSON_FEED_EXCERPT_CHAR_LIMIT)


def collect_html(source: HTMLSource) -> List[Item]:
    response = _fetch_response(source, is_rss=False)
    soup = BeautifulSoup(response.text, "lxml")
    items: List[Item] = []

    for row in soup.select(source.list_selector):
        row_soup = BeautifulSoup(str(row), "lxml")

        def get_field(name: str, default: str | list[str] = ""):
            if name not in source.fields:
                return default
            field = source.fields[name]
            return _extract_field(row_soup, field.selector, field.attr, field.multiple)

        title = get_field("title")
        url = get_field("url")
        description = get_field("description", "")
        comments = get_field("comments", [])
        media_urls = get_field("media", [])

        if isinstance(title, list):
            title = " ".join(title)
        if isinstance(url, list):
            url = url[0] if url else ""
        if isinstance(description, list):
            description = " ".join(description)
        if isinstance(comments, str):
            comments = [comments] if comments else []
        if isinstance(media_urls, str):
            media_urls = [media_urls] if media_urls else []

        url = urljoin(source.url, str(url))
        media = [MediaAsset(url=link, media_type=_guess_media_type(link)) for link in media_urls if link]

        items.append(
            Item(
                source=source.name,
                title=str(title),
                url=url,
                description=str(description),
                published_at=None,
                comments=comments,
                media=media,
                raw={"row_html": str(row)},
            )
        )
    return items


def collect_json_feed(source: JSONFeedSource) -> JSONFeedCollectResult:
    last_error: Exception | None = None
    for candidate_url in _candidate_urls(source):
        try:
            response = _fetch_response(source, is_rss=False, target_url=candidate_url)
            payload = response.json()
            entries = _normalize_json_feed_entries(_resolve_json_items(payload, source.items_path))
            items: list[Item] = []
            raw_items: list[dict[str, Any]] = []
            for entry in entries:
                title = _first_text(entry, "title", "name", "headline")
                url = _first_text(entry, "url", "canonical_url", "link", "external_url")
                description = _extract_json_description(entry)
                published_at = _parse_json_feed_published_at(
                    entry.get("published_at")
                    or entry.get("publishedAt")
                    or entry.get("published")
                    or entry.get("date_published")
                    or entry.get("created_at")
                    or entry.get("createdAt")
                    or entry.get("date")
                )
                comments = []
                raw_comments = entry.get("comments")
                if isinstance(raw_comments, list):
                    comments = [_coerce_text(item) for item in raw_comments if _coerce_text(item)]
                elif _coerce_text(raw_comments):
                    comments = [_coerce_text(raw_comments)]
                if not title and not url:
                    continue
                normalized_entry = dict(entry)
                raw_items.append(normalized_entry)
                items.append(
                    Item(
                        source=source.name,
                        title=title,
                        url=url,
                        description=description,
                        published_at=published_at,
                        comments=comments,
                        media=_extract_json_media(entry),
                        raw={
                            "json_item": normalized_entry,
                            "fetched_from_url": str(getattr(response, "url", "") or candidate_url),
                        },
                    )
                )
            return JSONFeedCollectResult(
                items=items,
                fetched_from_url=str(getattr(response, "url", "") or candidate_url),
                snapshot_payload={
                    "source": source.name,
                    "fetched_from_url": str(getattr(response, "url", "") or candidate_url),
                    "items_path": source.items_path,
                    "item_count": len(raw_items),
                    "items": raw_items,
                },
            )
        except (requests.RequestException, RuntimeError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            print(f"[collector][warn] {source.name} candidate failed: url={candidate_url} error={exc}")
            continue
    if last_error is not None:
        raise RuntimeError(f"JSON feed fetch failed for {source.name}: {last_error}") from last_error
    raise RuntimeError(f"JSON feed fetch failed for {source.name}")


def collect_sources(sources: List[RSSSource | HTMLSource | JSONFeedSource]) -> List[Item]:
    items: List[Item] = []
    for source in sources:
        try:
            if isinstance(source, RSSSource):
                source_items = collect_rss(source)
            elif isinstance(source, JSONFeedSource):
                source_items = collect_json_feed(source).items
            else:
                source_items = collect_html(source)
            items.extend(source_items)
            print(f"[collector] {source.name}: {len(source_items)} items")
        except Exception as exc:
            print(f"[collector][warn] {source.name} failed: {exc}")
    return items
