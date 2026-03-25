from __future__ import annotations

from pydantic import BaseModel, Field


class MediaAssetDTO(BaseModel):
    url: str
    media_type: str


class ContentDTO(BaseModel):
    content_id: str
    title: str
    canonical_url: str
    summary_text: str
    body_text: str | None = None
    published_at: str | None = None
    discovered_at: str | None = None
    updated_at: str
    language: str | None = None
    authors: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    media: list[MediaAssetDTO] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    source_count: int | None = None
