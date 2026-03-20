from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, HttpUrl, model_validator


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


class PublisherConfig(BaseModel):
    enabled: bool = False
    provider: Literal["typefully"] = "typefully"
    api_base: HttpUrl = "https://api.typefully.com/v2"
    api_key_env: str = "TYPEFULLY_API_KEY"
    social_set_id: Optional[str] = None
    publish_mode: Literal["draft", "now", "next-free-slot"] = "draft"
    x_enabled: bool = True
    dedup_channel: str = "publisher:typefully:x"
    max_post_length: int = 280
    tags: List[str] = []

    @model_validator(mode="after")
    def validate_enabled_config(self) -> "PublisherConfig":
        if self.enabled and not self.social_set_id:
            raise ValueError("publisher.social_set_id is required when publisher.enabled=true")
        return self


class AppConfig(BaseModel):
    schedule: ScheduleConfig
    sources: List[RSSSource | HTMLSource]
    filters: FilterConfig
    llm: LLMConfig
    media: MediaConfig
    storage: StorageConfig
    notifier: NotifierConfig
    publisher: PublisherConfig = Field(default_factory=PublisherConfig)
