from __future__ import annotations

import re
from typing import List

from scout_pipeline.models import Item, MediaAsset


IMG_REGEX = re.compile(r"<img[^>]+src=\"([^\"]+)\"")


def extract_media_from_html(html: str) -> List[MediaAsset]:
    media: List[MediaAsset] = []
    for match in IMG_REGEX.findall(html):
        if match:
            media.append(MediaAsset(url=match, media_type="image"))
    return media


def normalize_item(item: Item) -> Item:
    media = extract_media_from_html(item.description)
    if media:
        item.media.extend(media)
    item.description = re.sub(r"<[^>]+>", " ", item.description)
    item.description = re.sub(r"\s+", " ", item.description).strip()
    return item


def normalize_items(items: List[Item]) -> List[Item]:
    return [normalize_item(item) for item in items]
