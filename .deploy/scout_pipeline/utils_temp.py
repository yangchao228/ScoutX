from __future__ import annotations

import os
from typing import Any

from scout_pipeline.config import AppConfig


def load_config_simple() -> AppConfig:
    # 硬编码配置，避免 YAML 依赖
    config_data = {
        "schedule": {"cron": "0 */2 * * *"},
        "sources": [
            {"type": "rss", "name": "36kr_ai_search", "url": "http://127.0.0.1:1200/36kr/search/articles/AI"},
            {"type": "rss", "name": "36kr_newsflashes", "url": "http://127.0.0.1:1200/36kr/newsflashes"},
        ],
        "filters": {
            "allow_keywords": ["AI", "工具", "模型", "生成", "自动"],
            "deny_keywords": ["招聘", "课程", "卖课"],
            "min_score": 7
        },
        "llm": {
            "enabled": False,
            "provider": "openai",
            "api_base": "https://api.openai.com/v1",
            "api_key_env": "OPENAI_API_KEY",
            "model": "gpt-3.5-turbo",
            "temperature": 0.7
        },
        "media": {
            "download_dir": "media",
            "max_mb": 50
        },
        "storage": {
            "sqlite_path": "scout.db"
        },
        "notifier": {
            "feishu_webhook": None,
            "telegram_bot_token_env": None,
            "telegram_chat_id": None
        }
    }
    return AppConfig.model_validate(config_data)


def load_config(path: str) -> AppConfig:
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as handle:
            data: dict[str, Any] = yaml.safe_load(handle)
        return AppConfig.model_validate(data)
    except ImportError:
        print(f"Warning: PyYAML not found, using default config instead of {path}")
        return load_config_simple()


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing env var: {name}")
    return value