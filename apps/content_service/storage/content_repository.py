from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from apps.content_service.normalizers.content_normalizer import compute_content_id
from apps.content_service.schemas.content import ContentDTO, MediaAssetDTO
from apps.content_service.storage.models import ContentRecord
from scout_pipeline.models import Item


def _parse_rfc3339(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _format_rfc3339(value: datetime | None) -> str | None:
    if value is None:
        return None
    dt = value.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def _encode_cursor(item: ContentRecord) -> str:
    updated_at = _format_rfc3339(item.updated_at) or ""
    return f"{updated_at}|{item.content_id}"


@dataclass(frozen=True)
class CursorToken:
    updated_at: datetime
    content_id: str


def _decode_cursor(cursor: str) -> CursorToken:
    updated_at, _, content_id = cursor.partition("|")
    if not updated_at or not content_id:
        raise ValueError("invalid cursor format")
    return CursorToken(updated_at=_parse_rfc3339(updated_at), content_id=content_id)


def _to_content_dto(record: ContentRecord) -> ContentDTO:
    media = [
        MediaAssetDTO(
            url=str(asset.get("url") or "").strip(),
            media_type=str(asset.get("media_type") or "image").strip() or "image",
        )
        for asset in record.media or []
        if str(asset.get("url") or "").strip()
    ]
    return ContentDTO(
        content_id=record.content_id,
        title=record.title,
        canonical_url=record.canonical_url,
        summary_text=record.summary_text,
        body_text=record.body_text or None,
        published_at=_format_rfc3339(record.published_at),
        discovered_at=_format_rfc3339(record.discovered_at),
        updated_at=_format_rfc3339(record.updated_at) or "",
        language=record.language,
        authors=list(record.authors or []),
        tags=list(record.tags or []),
        media=media,
        sources=list(record.sources or []),
        source_count=record.source_count,
    )


@dataclass(frozen=True)
class UpsertStats:
    created: int = 0
    updated: int = 0


@dataclass
class ContentRepository:
    session: Session

    def list_contents(
        self,
        *,
        updated_since: str | None = None,
        published_since: str | None = None,
        source: str | None = None,
        tag: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[ContentDTO], str | None]:
        stmt: Select[tuple[ContentRecord]] = select(ContentRecord)

        if updated_since:
            stmt = stmt.where(ContentRecord.updated_at > _parse_rfc3339(updated_since))
        if published_since:
            stmt = stmt.where(ContentRecord.published_at.is_not(None))
            stmt = stmt.where(ContentRecord.published_at > _parse_rfc3339(published_since))
        if source:
            stmt = stmt.where(ContentRecord.sources.contains([source]))
        if tag:
            stmt = stmt.where(ContentRecord.tags.contains([tag]))

        if cursor:
            token = _decode_cursor(cursor)
            stmt = stmt.where(
                (ContentRecord.updated_at > token.updated_at)
                | (
                    (ContentRecord.updated_at == token.updated_at)
                    & (ContentRecord.content_id > token.content_id)
                )
            )

        stmt = stmt.order_by(ContentRecord.updated_at.asc(), ContentRecord.content_id.asc()).limit(limit + 1)
        rows = list(self.session.execute(stmt).scalars().all())
        next_cursor = None
        if len(rows) > limit:
            next_cursor = _encode_cursor(rows[limit - 1])
            rows = rows[:limit]
        return [_to_content_dto(row) for row in rows], next_cursor

    def get_content(self, content_id: str) -> ContentDTO | None:
        stmt = select(ContentRecord).where(ContentRecord.content_id == content_id)
        row = self.session.execute(stmt).scalar_one_or_none()
        if row is None:
            return None
        return _to_content_dto(row)

    def list_recent_contents(
        self,
        *,
        limit: int = 50,
        published_since: str | None = None,
    ) -> list[ContentDTO]:
        stmt: Select[tuple[ContentRecord]] = select(ContentRecord)
        if published_since:
            stmt = stmt.where(ContentRecord.published_at.is_not(None))
            stmt = stmt.where(ContentRecord.published_at > _parse_rfc3339(published_since))
        stmt = stmt.order_by(
            ContentRecord.published_at.desc().nullslast(),
            ContentRecord.updated_at.desc(),
            ContentRecord.content_id.desc(),
        ).limit(limit)
        rows = list(self.session.execute(stmt).scalars().all())
        return [_to_content_dto(row) for row in rows]

    def upsert_items(self, items: list[Item]) -> UpsertStats:
        created = 0
        updated = 0
        for item in items:
            content_id = compute_content_id(item)
            existing = self.session.get(ContentRecord, content_id)
            payload = self._build_upsert_payload(item, content_id, existing)

            stmt = insert(ContentRecord).values(**payload)
            stmt = stmt.on_conflict_do_update(
                index_elements=[ContentRecord.content_id],
                set_={
                    "title": payload["title"],
                    "canonical_url": payload["canonical_url"],
                    "summary_text": payload["summary_text"],
                    "body_text": payload["body_text"],
                    "published_at": payload["published_at"],
                    "updated_at": payload["updated_at"],
                    "language": payload["language"],
                    "authors": payload["authors"],
                    "tags": payload["tags"],
                    "media": payload["media"],
                    "sources": payload["sources"],
                    "source_count": payload["source_count"],
                },
            )
            self.session.execute(stmt)
            if existing is None:
                created += 1
            else:
                updated += 1
        return UpsertStats(created=created, updated=updated)

    def _build_upsert_payload(
        self,
        item: Item,
        content_id: str,
        existing: ContentRecord | None,
    ) -> dict[str, Any]:
        published_at = _parse_rfc3339(item.published_at) if item.published_at else None
        updated_at = datetime.now(timezone.utc)
        existing_sources = list(existing.sources or []) if existing else []
        existing_media = list(existing.media or []) if existing else []
        new_media = [
            {
                "url": media.url,
                "media_type": media.media_type,
            }
            for media in item.media
            if media.url
        ]
        merged_sources = list(dict.fromkeys(existing_sources + ([item.source] if item.source else [])))
        merged_media = list(dict.fromkeys((asset["url"], asset["media_type"]) for asset in existing_media + new_media))
        return {
            "content_id": content_id,
            "title": (item.title or "").strip(),
            "canonical_url": (item.url or "").strip(),
            "summary_text": (item.description or "").strip(),
            "body_text": "",
            "published_at": published_at,
            "updated_at": updated_at,
            "language": None,
            "authors": [],
            "tags": [],
            "media": [{"url": url, "media_type": media_type} for url, media_type in merged_media],
            "sources": merged_sources,
            "source_count": len(merged_sources),
        }
