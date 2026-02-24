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
    if config.max_mb <= 0:
        return item

    os.makedirs(config.download_dir, exist_ok=True)
    max_bytes = config.max_mb * 1024 * 1024

    # 避免一个条目包含大量图片时卡住整个 pipeline。
    for media in item.media[:3]:
        local_path: str | None = None
        try:
            response = requests.get(media.url, timeout=(5, 20), stream=True)
            response.raise_for_status()

            content_length = int(response.headers.get("Content-Length", "0") or 0)
            if content_length and content_length > max_bytes:
                continue
            filename = _safe_filename(media.url)
            local_path = os.path.join(config.download_dir, filename)
            with open(local_path, "wb") as handle:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        downloaded += len(chunk)
                        if downloaded > max_bytes:
                            raise RuntimeError("media exceeds max_mb")
                        handle.write(chunk)
            media.local_path = local_path
        except Exception:
            if local_path:
                try:
                    if os.path.exists(local_path):
                        os.remove(local_path)
                except Exception:
                    pass
            continue
    return item
