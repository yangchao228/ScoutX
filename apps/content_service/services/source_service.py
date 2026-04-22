from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from apps.content_service.schemas.source import (
    HTMLSourceValidationRequest,
    JSONFeedSourceValidationRequest,
    RSSSourceValidationRequest,
    SourceDTO,
    SourceSnapshotInfoDTO,
    SourceValidationResultDTO,
)
from apps.content_service.services.source_validation import validate_source_payload
from apps.content_service.storage.source_repository import SourceRepository
from apps.content_service.storage.source_snapshot_repository import SourceSnapshotRepository, SourceSnapshotSummary


def _format_rfc3339(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _snapshot_info(summary: SourceSnapshotSummary | None) -> SourceSnapshotInfoDTO:
    if summary is None:
        return SourceSnapshotInfoDTO(has_snapshot=False)
    return SourceSnapshotInfoDTO(
        has_snapshot=True,
        snapshot_fetched_at=_format_rfc3339(summary.fetched_at),
        snapshot_fetched_from_url=summary.fetched_from_url,
        snapshot_item_count=summary.item_count,
    )


@dataclass
class SourceService:
    session: Session

    def list_sources(self, *, enabled: bool | None = None, source_type: str | None = None) -> list[SourceDTO]:
        items = SourceRepository(self.session).list_sources(enabled=enabled, source_type=source_type)
        snapshot_map = SourceSnapshotRepository(self.session).list_latest_snapshots_by_source_names(
            [item.name for item in items]
        )
        return [
            item.model_copy(update={"snapshot": _snapshot_info(snapshot_map.get(item.name))})
            for item in items
        ]

    def validate_source(
        self,
        request: RSSSourceValidationRequest | HTMLSourceValidationRequest | JSONFeedSourceValidationRequest,
    ) -> SourceValidationResultDTO:
        return validate_source_payload(request)
