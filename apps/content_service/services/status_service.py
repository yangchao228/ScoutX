from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.content_service.schemas.status import (
    ContentStatsDTO,
    SchedulerRunDTO,
    SourceFailureDTO,
    SourceSlowDTO,
    SourceStatsDTO,
    StatusDTO,
)
from apps.content_service.settings import load_settings
from apps.content_service.storage.models import ContentRecord, SourceRecord
from apps.content_service.storage.runtime_state_repository import RuntimeStateRepository


def _format_rfc3339(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


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
        total = int(
            self.session.execute(
                select(func.count()).select_from(SourceRecord).where(SourceRecord.enabled.is_(True))
            ).scalar_one()
            or 0
        )
        success = int(
            self.session.execute(
                select(func.count())
                .select_from(SourceRecord)
                .where(SourceRecord.enabled.is_(True), SourceRecord.last_status == "success")
            ).scalar_one()
            or 0
        )
        failed = int(
            self.session.execute(
                select(func.count())
                .select_from(SourceRecord)
                .where(SourceRecord.enabled.is_(True), SourceRecord.last_status == "failed")
            ).scalar_one()
            or 0
        )
        slow = int(
            self.session.execute(
                select(func.count())
                .select_from(SourceRecord)
                .where(
                    SourceRecord.enabled.is_(True),
                    SourceRecord.last_duration_ms.is_not(None),
                    SourceRecord.last_duration_ms >= settings.slow_source_threshold_ms,
                )
            ).scalar_one()
            or 0
        )
        never_run = int(
            self.session.execute(
                select(func.count())
                .select_from(SourceRecord)
                .where(SourceRecord.enabled.is_(True), SourceRecord.last_run_at.is_(None))
            ).scalar_one()
            or 0
        )
        rows = self.session.execute(
            select(SourceRecord)
            .where(SourceRecord.enabled.is_(True), SourceRecord.last_status == "failed")
            .order_by(SourceRecord.last_run_at.desc().nullslast(), SourceRecord.name.asc())
            .limit(5)
        ).scalars().all()
        slow_rows = self.session.execute(
            select(SourceRecord)
            .where(
                SourceRecord.enabled.is_(True),
                SourceRecord.last_duration_ms.is_not(None),
                SourceRecord.last_duration_ms >= settings.slow_source_threshold_ms,
            )
            .order_by(SourceRecord.last_duration_ms.desc(), SourceRecord.last_run_at.desc().nullslast())
            .limit(5)
        ).scalars().all()
        return SourceStatsDTO(
            total=total,
            success=success,
            failed=failed,
            slow=slow,
            never_run=never_run,
            recent_failures=[
                SourceFailureDTO(
                    name=row.name,
                    type=row.source_type,
                    last_run_at=_format_rfc3339(row.last_run_at),
                    last_error=row.last_error,
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
