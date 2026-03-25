from __future__ import annotations

import os

from scout_pipeline.config import AppConfig
from scout_pipeline.utils import load_config


def load_source_config() -> AppConfig:
    path = os.getenv("CONTENT_SERVICE_SOURCE_CONFIG_PATH", "config.yaml").strip() or "config.yaml"
    return load_config(path)
