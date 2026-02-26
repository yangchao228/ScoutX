from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, HttpUrl


class FieldSelector(BaseModel):
    selector: str
    attr: Optional[str] = None
    multiple: bool = False


class RSSSource(BaseModel):
    type: Literal["rss"]
    name: str
    url: HttpUrl


class HTMLSource(BaseModel):
    type: Literal["html"]
    name: str
    url: HttpUrl
    list_selector: str
    fields: Dict[str, FieldSelector]


class FilterConfig(BaseModel):
    allow_keywords: List[str] = []
    deny_keywords: List[str] = []
    min_score: float = 7.0


class LLMConfig(BaseModel):
    enabled: bool = True
    provider: Literal["openai", "deepseek"]
    api_base: HttpUrl
    api_key_env: str
    model: str
    temperature: float = 0.7
    filter_system_prompt: str
    filter_user_prompt: str
    creator_system_prompt: str = ""
    creator_user_prompt: str


class MediaConfig(BaseModel):
    download_dir: str = "media"
    max_mb: int = 50


class StorageConfig(BaseModel):
    sqlite_path: str = "scout.db"


class NotifierConfig(BaseModel):
    feishu_webhook: Optional[HttpUrl] = None


class ScheduleConfig(BaseModel):
    cron: str


class AppConfig(BaseModel):
    schedule: ScheduleConfig
    sources: List[RSSSource | HTMLSource]
    filters: FilterConfig
    llm: LLMConfig
    media: MediaConfig
    storage: StorageConfig
    notifier: NotifierConfig
