from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from croniter import croniter

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.content_service.schemas.status import (
    ContentStatsDTO,
    SchedulerRunDTO,
    SourceEmptyDTO,
    SourceFailureDTO,
    SourceSnapshotInfoDTO,
    SourceStaleDTO,
    SourceSlowDTO,
    SourceStatsDTO,
    StatusDTO,
)
from apps.content_service.settings import load_settings
from apps.content_service.storage.models import ContentRecord, SourceRecord
from apps.content_service.storage.runtime_state_repository import RuntimeStateRepository
from apps.content_service.storage.source_snapshot_repository import SourceSnapshotRepository, SourceSnapshotSummary


def _format_rfc3339(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _schedule_interval_minutes(schedule: str, now: datetime) -> int:
    try:
        iterator = croniter(schedule, now)
        latest = iterator.get_prev(datetime)
        previous = croniter(schedule, latest).get_prev(datetime)
    except Exception:
        return 360
    interval_seconds = max(60, int((latest - previous).total_seconds()))
    return max(1, interval_seconds // 60)


def _stale_threshold_minutes(schedule: str, now: datetime) -> int:
    return max(60, _schedule_interval_minutes(schedule, now) * 2)


def _compute_stale_minutes(record: SourceRecord, now: datetime) -> int | None:
    if record.last_success_at is None:
        return None
    return max(0, int((now - record.last_success_at).total_seconds() // 60))


def _is_stale_source(record: SourceRecord, now: datetime) -> tuple[bool, int | None]:
    stale_minutes = _compute_stale_minutes(record, now)
    if stale_minutes is None:
        return True, None
    return stale_minutes >= _stale_threshold_minutes(record.schedule, now), stale_minutes


def _snapshot_info(summary: SourceSnapshotSummary | None) -> SourceSnapshotInfoDTO:
    if summary is None:
        return SourceSnapshotInfoDTO(has_snapshot=False)
    return SourceSnapshotInfoDTO(
        has_snapshot=True,
        snapshot_fetched_at=_format_rfc3339(summary.fetched_at),
        snapshot_fetched_from_url=summary.fetched_from_url,
        snapshot_item_count=summary.item_count,
    )


def _is_empty_feed_source(record: SourceRecord, summary: SourceSnapshotSummary | None) -> bool:
    return (
        record.last_status == "success"
        and summary is not None
        and int(summary.item_count or 0) == 0
    )


def _effective_slow_threshold_ms(record: SourceRecord, default_threshold_ms: int) -> int:
    config = record.config_json or {}
    configured = config.get("slow_threshold_ms")
    if isinstance(configured, int) and configured > 0:
        return configured
    try:
        parsed = int(configured)
    except (TypeError, ValueError):
        return default_threshold_ms
    return parsed if parsed > 0 else default_threshold_ms


def _is_slow_source(record: SourceRecord, default_threshold_ms: int) -> bool:
    duration_ms = int(record.last_duration_ms or 0)
    if duration_ms <= 0:
        return False
    return duration_ms >= _effective_slow_threshold_ms(record, default_threshold_ms)


@dataclass
class StatusService:
    session: Session

    def get_status(self) -> StatusDTO:
        settings = load_settings()
        now = datetime.now(timezone.utc)
        content_stats = self._build_content_stats()
        source_stats = self._build_source_stats()
        return StatusDTO(
            service=settings.app_name,
            env=settings.app_env,
            time=_format_rfc3339(now) or "",
            contents=content_stats,
            sources=source_stats,
            latest_scheduler_run=self._build_latest_scheduler_run(now, failed_sources=source_stats.failed),
        )

    def _build_content_stats(self) -> ContentStatsDTO:
        total = int(
            self.session.execute(
                select(func.count()).select_from(ContentRecord)
            ).scalar_one()
            or 0
        )
        latest_updated_at = self.session.execute(
            select(func.max(ContentRecord.updated_at))
        ).scalar_one_or_none()
        return ContentStatsDTO(
            total=total,
            latest_updated_at=_format_rfc3339(latest_updated_at),
        )

    def _build_source_stats(self) -> SourceStatsDTO:
        settings = load_settings()
        now = datetime.now(timezone.utc)
        enabled_rows = self.session.execute(
            select(SourceRecord)
            .where(SourceRecord.enabled.is_(True))
            .order_by(SourceRecord.name.asc())
        ).scalars().all()
        total = len(enabled_rows)
        success = sum(1 for row in enabled_rows if row.last_status == "success")
        failed = sum(1 for row in enabled_rows if row.last_status == "failed")
        never_run = sum(1 for row in enabled_rows if row.last_run_at is None)
        slow_rows = [
            row for row in enabled_rows
            if _is_slow_source(row, settings.slow_source_threshold_ms)
        ]
        slow = len(slow_rows)
        rows = self.session.execute(
            select(SourceRecord)
            .where(SourceRecord.enabled.is_(True), SourceRecord.last_status == "failed")
            .order_by(SourceRecord.last_run_at.desc().nullslast(), SourceRecord.name.asc())
            .limit(5)
        ).scalars().all()
        slow_rows.sort(
            key=lambda row: (
                -int(row.last_duration_ms or 0),
                _format_rfc3339(row.last_run_at) or "",
                row.name,
            )
        )
        snapshot_map = SourceSnapshotRepository(self.session).list_latest_snapshots_by_source_names(
            [row.name for row in enabled_rows]
        )
        stale_rows: list[tuple[SourceRecord, int | None]] = []
        empty_rows: list[SourceRecord] = []
        for row in enabled_rows:
            if _is_empty_feed_source(row, snapshot_map.get(row.name)):
                empty_rows.append(row)
            is_stale, stale_minutes = _is_stale_source(row, now)
            if is_stale:
                stale_rows.append((row, stale_minutes))
        stale_rows.sort(
            key=lambda item: (
                0 if item[1] is None else 1,
                0 if item[1] is None else -item[1],
                item[0].name,
            )
        )
        empty_rows.sort(
            key=lambda row: (
                0 if row.last_success_at is None else 1,
                _format_rfc3339(row.last_success_at) or "",
                row.name,
            ),
            reverse=True,
        )
        return SourceStatsDTO(
            total=total,
            success=success,
            failed=failed,
            slow=slow,
            stale=len(stale_rows),
            empty=len(empty_rows),
            never_run=never_run,
            recent_failures=[
                SourceFailureDTO(
                    name=row.name,
                    type=row.source_type,
                    last_run_at=_format_rfc3339(row.last_run_at),
                    last_success_at=_format_rfc3339(row.last_success_at),
                    last_error=row.last_error,
                    consecutive_failures=int(row.consecutive_failures or 0),
                    snapshot=_snapshot_info(snapshot_map.get(row.name)),
                )
                for row in rows
            ],
            recent_slow_sources=[
                SourceSlowDTO(
                    name=row.name,
                    type=row.source_type,
                    last_run_at=_format_rfc3339(row.last_run_at),
                    last_duration_ms=int(row.last_duration_ms or 0),
                )
                for row in slow_rows
            ],
            recent_stale_sources=[
                SourceStaleDTO(
                    name=row.name,
                    type=row.source_type,
                    last_success_at=_format_rfc3339(row.last_success_at),
                    stale_minutes=stale_minutes,
                    consecutive_failures=int(row.consecutive_failures or 0),
                    snapshot=_snapshot_info(snapshot_map.get(row.name)),
                )
                for row, stale_minutes in stale_rows[:5]
            ],
            recent_empty_sources=[
                SourceEmptyDTO(
                    name=row.name,
                    type=row.source_type,
                    last_success_at=_format_rfc3339(row.last_success_at),
                    consecutive_failures=int(row.consecutive_failures or 0),
                    snapshot=_snapshot_info(snapshot_map.get(row.name)),
                )
                for row in empty_rows[:5]
            ],
        )

    def _build_latest_scheduler_run(self, now: datetime, *, failed_sources: int) -> SchedulerRunDTO | None:
        payload = RuntimeStateRepository(self.session).load_latest_scheduler_run()
        if not payload:
            return None
        return SchedulerRunDTO(
            time=str(payload.get("time") or _format_rfc3339(now) or ""),
            collected=int(payload.get("collected") or 0),
            normalized=int(payload.get("normalized") or 0),
            created=int(payload.get("created") or 0),
            updated=int(payload.get("updated") or 0),
            failed_sources=int(payload.get("failed_sources") or failed_sources),
            slow_sources=int(payload.get("slow_sources") or 0),
        )
