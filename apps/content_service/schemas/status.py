from __future__ import annotations

from pydantic import BaseModel, Field


class ContentStatsDTO(BaseModel):
    total: int
    latest_updated_at: str | None = None


class SourceFailureDTO(BaseModel):
    name: str
    type: str
    last_run_at: str | None = None
    last_error: str | None = None


class SourceSlowDTO(BaseModel):
    name: str
    type: str
    last_run_at: str | None = None
    last_duration_ms: int


class SourceStatsDTO(BaseModel):
    total: int
    success: int
    failed: int
    slow: int
    never_run: int
    recent_failures: list[SourceFailureDTO] = Field(default_factory=list)
    recent_slow_sources: list[SourceSlowDTO] = Field(default_factory=list)


class SchedulerRunDTO(BaseModel):
    time: str
    collected: int
    normalized: int
    created: int
    updated: int
    failed_sources: int
    slow_sources: int = 0


class StatusDTO(BaseModel):
    service: str
    env: str
    time: str
    contents: ContentStatsDTO
    sources: SourceStatsDTO
    latest_scheduler_run: SchedulerRunDTO | None = None
