from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from apps.content_service.schemas.content import ContentDTO


class SubscriptionFiltersDTO(BaseModel):
    sources: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    keywords_allow: list[str] = Field(default_factory=list)
    keywords_deny: list[str] = Field(default_factory=list)
    published_within_hours: int | None = None
    max_items: int | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class SubscriptionCreateRequest(BaseModel):
    name: str
    timezone: str
    cadence: str
    delivery_channel: str
    language: str
    filters: SubscriptionFiltersDTO = Field(default_factory=SubscriptionFiltersDTO)


class SubscriptionUpdateRequest(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    timezone: str | None = None
    cadence: str | None = None
    delivery_channel: str | None = None
    language: str | None = None
    filters: SubscriptionFiltersDTO | None = None


class SubscriptionDTO(BaseModel):
    subscription_id: str
    name: str
    enabled: bool
    timezone: str
    cadence: str
    delivery_channel: str
    language: str
    filters: SubscriptionFiltersDTO = Field(default_factory=SubscriptionFiltersDTO)
    last_cursor: str | None = None
    last_run_at: str | None = None
    created_at: str
    updated_at: str


class SubscriptionRunDTO(BaseModel):
    run_id: str
    subscription_id: str
    status: str
    delivered_count: int
    started_at: str
    completed_at: str | None = None
    preview: list[ContentDTO] = Field(default_factory=list)
