from __future__ import annotations

import hashlib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from scout_pipeline.extractor import normalize_item
from scout_pipeline.models import Item


TRACKING_QUERY_PREFIXES = ("utm_",)
TRACKING_QUERY_NAMES = {"spm", "from", "fromSource", "track", "tracking"}


def canonicalize_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    parts = urlsplit(raw)
    filtered_query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key not in TRACKING_QUERY_NAMES and not key.lower().startswith(TRACKING_QUERY_PREFIXES)
    ]
    normalized = urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path,
            urlencode(filtered_query, doseq=True),
            "",
        )
    )
    return normalized


def compute_content_id(item: Item) -> str:
    canonical_url = canonicalize_url(item.url)
    key = canonical_url or (item.title or "").strip()
    digest = hashlib.md5(key.encode("utf-8")).hexdigest()
    return f"cnt_{digest}"


def normalize_content_item(item: Item) -> Item:
    normalized = normalize_item(item)
    normalized.url = canonicalize_url(normalized.url)
    return normalized
