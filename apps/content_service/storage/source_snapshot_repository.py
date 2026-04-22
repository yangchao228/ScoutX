from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from apps.content_service.storage.models import SourceRecord, SourceSnapshotRecord
from apps.content_service.storage.source_ids import compute_source_id


@dataclass(frozen=True)
class SourceSnapshotSummary:
    source_name: str
    fetched_at: datetime
    fetched_from_url: str | None
    item_count: int


@dataclass
class SourceSnapshotRepository:
    session: Session

    def save_latest_snapshot(
        self,
        *,
        source_name: str,
        fetched_from_url: str | None,
        item_count: int,
        payload_json: dict[str, Any],
    ) -> None:
        now = datetime.now(timezone.utc)
        source_id = compute_source_id(source_name)
        stmt = insert(SourceSnapshotRecord).values(
            source_id=source_id,
            fetched_at=now,
            fetched_from_url=fetched_from_url,
            item_count=item_count,
            payload_json=payload_json,
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[SourceSnapshotRecord.source_id],
            set_={
                "fetched_at": now,
                "fetched_from_url": fetched_from_url,
                "item_count": item_count,
                "payload_json": payload_json,
                "updated_at": now,
            },
        )
        self.session.execute(stmt)

    def list_latest_snapshots_by_source_names(self, source_names: list[str]) -> dict[str, SourceSnapshotSummary]:
        normalized_names = [name.strip() for name in source_names if name and name.strip()]
        if not normalized_names:
            return {}
        stmt = (
            select(SourceRecord.name, SourceSnapshotRecord)
            .join(SourceSnapshotRecord, SourceSnapshotRecord.source_id == SourceRecord.source_id)
            .where(SourceRecord.name.in_(normalized_names))
        )
        rows = self.session.execute(stmt).all()
        return {
            str(source_name): SourceSnapshotSummary(
                source_name=str(source_name),
                fetched_at=record.fetched_at,
                fetched_from_url=record.fetched_from_url,
                item_count=int(record.item_count or 0),
            )
            for source_name, record in rows
        }
