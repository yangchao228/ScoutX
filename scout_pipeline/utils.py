from __future__ import annotations

import os
from typing import Any

import yaml

from scout_pipeline.config import AppConfig


def load_config(path: str) -> AppConfig:
    with open(path, "r", encoding="utf-8") as handle:
        data: dict[str, Any] = yaml.safe_load(handle)
    return AppConfig.model_validate(data)


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing env var: {name}")
    return value
