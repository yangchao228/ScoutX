from __future__ import annotations

import calendar
from datetime import datetime, timezone
from typing import List
from urllib.parse import urljoin

import feedparser
import requests
from bs4 import BeautifulSoup

from scout_pipeline.config import HTMLSource, RSSSource
from scout_pipeline.models import Item, MediaAsset


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


def collect_rss(source: RSSSource) -> List[Item]:
    response = requests.get(
        str(source.url),
        timeout=30,
        headers={
            "User-Agent": "Mozilla/5.0 (ScoutX/1.0; +https://github.com/)",
            "Accept": "application/rss+xml,application/atom+xml,application/xml,text/xml,*/*",
        },
    )
    response.raise_for_status()
    feed = feedparser.parse(response.content)

    if getattr(feed, "bozo", 0) and not feed.entries:
        raise RuntimeError(f"Invalid RSS feed: {source.name} ({source.url})")

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

        items.append(
            Item(
                source=source.name,
                title=title,
                url=url,
                description=description,
                published_at=_extract_entry_published_at(entry),
                comments=comments,
                media=media,
                raw={"entry": entry},
            )
        )
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


def collect_html(source: HTMLSource) -> List[Item]:
    response = requests.get(str(source.url), timeout=30)
    response.raise_for_status()
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


def collect_sources(sources: List[RSSSource | HTMLSource]) -> List[Item]:
    items: List[Item] = []
    for source in sources:
        try:
            if isinstance(source, RSSSource):
                source_items = collect_rss(source)
            else:
                source_items = collect_html(source)
            items.extend(source_items)
            print(f"[collector] {source.name}: {len(source_items)} items")
        except Exception as exc:
            print(f"[collector][warn] {source.name} failed: {exc}")
    return items
