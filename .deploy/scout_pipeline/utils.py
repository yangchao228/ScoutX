from __future__ import annotations

import os
import re
from typing import Any

import yaml

from scout_pipeline.config import AppConfig

_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)(?::([^}]*))?\}")


def _expand_env(value: Any) -> Any:
    """支持在 config.yaml 中写 ${VAR} 或 ${VAR:default}。"""

    if isinstance(value, str):
        if "${" not in value:
            return value

        def _repl(match: re.Match[str]) -> str:
            var = match.group(1)
            default = match.group(2)
            resolved = os.getenv(var, default)
            if resolved is None:
                raise RuntimeError(f"Missing env var in config: {var}")
            return resolved

        return _ENV_PATTERN.sub(_repl, value)

    if isinstance(value, list):
        return [_expand_env(v) for v in value]

    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}

    return value


def load_config(path: str) -> AppConfig:
    with open(path, "r", encoding="utf-8") as handle:
        data: dict[str, Any] = yaml.safe_load(handle)
    data = _expand_env(data)
    return AppConfig.model_validate(data)


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing env var: {name}")
    return value
