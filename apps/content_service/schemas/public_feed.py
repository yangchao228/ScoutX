from __future__ import annotations

from pydantic import BaseModel, Field


class PublicFeedItemDTO(BaseModel):
    content_id: str
    title: str
    summary_text: str
    canonical_url: str
    published_at: str | None = None
    updated_at: str
    language: str | None = None
    sources: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class PublicFeedDTO(BaseModel):
    generated_at: str
    items: list[PublicFeedItemDTO] = Field(default_factory=list)


class PublicFeedMetaDTO(BaseModel):
    generated_at: str
    feed_url: str
    default_limit: int
    default_hours: int
    cache_ttl_seconds: int
