from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Select, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from apps.content_service.schemas.source import SourceDTO
from apps.content_service.storage.source_ids import compute_source_id
from apps.content_service.storage.models import SourceRecord


def _format_rfc3339(value: datetime | None) -> str | None:
    if value is None:
        return None
    dt = value.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def _to_source_dto(record: SourceRecord) -> SourceDTO:
    return SourceDTO(
        source_id=record.source_id,
        name=record.name,
        type=record.source_type,
        enabled=record.enabled,
        schedule=record.schedule,
        last_run_at=_format_rfc3339(record.last_run_at),
        last_status=record.last_status,
        last_error=record.last_error,
        last_duration_ms=record.last_duration_ms,
    )


@dataclass
class SourceRepository:
    session: Session

    def sync_source_configs(self, source_configs: list[dict[str, Any]], schedule: str) -> None:
        seen_names = set()
        now = datetime.now(timezone.utc)
        for payload in source_configs:
            name = str(payload.get("name") or "").strip()
            if not name or name in seen_names:
                continue
            seen_names.add(name)
            source_type = str(payload.get("type") or "").strip()
            stmt = insert(SourceRecord).values(
                source_id=compute_source_id(name),
                name=name,
                type=source_type,
                enabled=True,
                schedule=schedule,
                config_json=payload,
                updated_at=now,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[SourceRecord.name],
                set_={
                    "type": source_type,
                    "enabled": True,
                    "schedule": schedule,
                    "config_json": payload,
                    "updated_at": now,
                },
            )
            self.session.execute(stmt)

        stale_stmt = update(SourceRecord).values(enabled=False, updated_at=now)
        if seen_names:
            stale_stmt = stale_stmt.where(SourceRecord.name.not_in(seen_names))
        self.session.execute(stale_stmt)

    def list_sources(self, *, enabled: bool | None = None, source_type: str | None = None) -> list[SourceDTO]:
        stmt: Select[tuple[SourceRecord]] = select(SourceRecord)
        if enabled is not None:
            stmt = stmt.where(SourceRecord.enabled.is_(enabled))
        if source_type:
            stmt = stmt.where(SourceRecord.source_type == source_type)
        stmt = stmt.order_by(SourceRecord.name.asc())
        return [_to_source_dto(row) for row in self.session.execute(stmt).scalars().all()]

    def mark_run_result(
        self,
        name: str,
        *,
        status: str,
        error: str | None = None,
        duration_ms: int | None = None,
    ) -> None:
        stmt = select(SourceRecord).where(SourceRecord.name == name)
        record = self.session.execute(stmt).scalar_one_or_none()
        if record is None:
            return
        now = datetime.now(timezone.utc)
        record.last_run_at = now
        record.last_status = status
        record.last_error = error
        record.last_duration_ms = duration_ms
        record.updated_at = now
