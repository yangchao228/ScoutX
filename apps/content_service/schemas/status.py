from __future__ import annotations

from pydantic import BaseModel, Field


class ContentStatsDTO(BaseModel):
    total: int
    latest_updated_at: str | None = None


class SourceSnapshotInfoDTO(BaseModel):
    has_snapshot: bool = False
    snapshot_fetched_at: str | None = None
    snapshot_fetched_from_url: str | None = None
    snapshot_item_count: int | None = None


class SourceFailureDTO(BaseModel):
    name: str
    type: str
    last_run_at: str | None = None
    last_success_at: str | None = None
    last_error: str | None = None
    consecutive_failures: int = 0
    snapshot: SourceSnapshotInfoDTO = Field(default_factory=SourceSnapshotInfoDTO)


class SourceSlowDTO(BaseModel):
    name: str
    type: str
    last_run_at: str | None = None
    last_duration_ms: int


class SourceStaleDTO(BaseModel):
    name: str
    type: str
    last_success_at: str | None = None
    stale_minutes: int | None = None
    consecutive_failures: int = 0
    snapshot: SourceSnapshotInfoDTO = Field(default_factory=SourceSnapshotInfoDTO)


class SourceEmptyDTO(BaseModel):
    name: str
    type: str
    last_success_at: str | None = None
    consecutive_failures: int = 0
    snapshot: SourceSnapshotInfoDTO = Field(default_factory=SourceSnapshotInfoDTO)


class SourceStatsDTO(BaseModel):
    total: int
    success: int
    failed: int
    slow: int
    stale: int
    empty: int
    never_run: int
    recent_failures: list[SourceFailureDTO] = Field(default_factory=list)
    recent_slow_sources: list[SourceSlowDTO] = Field(default_factory=list)
    recent_stale_sources: list[SourceStaleDTO] = Field(default_factory=list)
    recent_empty_sources: list[SourceEmptyDTO] = Field(default_factory=list)


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
