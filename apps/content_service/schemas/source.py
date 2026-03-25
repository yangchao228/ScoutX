from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class FieldSelectorDTO(BaseModel):
    selector: str
    attr: str | None = None
    multiple: bool = False


class RSSSourceValidationRequest(BaseModel):
    type: Literal["rss"]
    name: str
    url: str


class HTMLSourceValidationRequest(BaseModel):
    type: Literal["html"]
    name: str
    url: str
    list_selector: str
    fields: dict[str, FieldSelectorDTO] = Field(default_factory=dict)


class SourceDTO(BaseModel):
    source_id: str
    name: str
    type: str
    enabled: bool
    schedule: str
    last_run_at: str | None = None
    last_status: str | None = None
    last_error: str | None = None
    last_duration_ms: int | None = None


class SourceValidationResultDTO(BaseModel):
    ok: bool
    name: str
    type: str
    status_code: int | None = None
    item_count: int | None = None
    sample_titles: list[str] = Field(default_factory=list)
    message: str | None = None
