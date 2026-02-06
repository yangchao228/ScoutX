from __future__ import annotations

import os
from typing import List
from urllib.parse import urlparse

import requests

from scout_pipeline.config import MediaConfig
from scout_pipeline.models import Item, MediaAsset


def _safe_filename(url: str) -> str:
    path = urlparse(url).path
    name = os.path.basename(path) or "asset"
    return name.split("?")[0]


def download_media(config: MediaConfig, item: Item) -> Item:
    os.makedirs(config.download_dir, exist_ok=True)
    max_bytes = config.max_mb * 1024 * 1024

    for media in item.media:
        try:
            response = requests.get(media.url, timeout=30, stream=True)
            response.raise_for_status()
            if int(response.headers.get("Content-Length", "0")) > max_bytes:
                continue
            filename = _safe_filename(media.url)
            local_path = os.path.join(config.download_dir, filename)
            with open(local_path, "wb") as handle:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        handle.write(chunk)
            media.local_path = local_path
        except Exception:
            continue
    return item
