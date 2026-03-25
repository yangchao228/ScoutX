from __future__ import annotations

from dataclasses import dataclass
from sqlalchemy.orm import Session

from apps.content_service.schemas.content import ContentDTO
from apps.content_service.storage.content_repository import ContentRepository


@dataclass
class ContentQuery:
    updated_since: str | None = None
    published_since: str | None = None
    source: str | None = None
    tag: str | None = None
    limit: int = 50
    cursor: str | None = None


@dataclass
class ContentService:
    session: Session

    def list_contents(self, query: ContentQuery) -> tuple[list[ContentDTO], str | None]:
        repo = ContentRepository(self.session)
        return repo.list_contents(
            updated_since=query.updated_since,
            published_since=query.published_since,
            source=query.source,
            tag=query.tag,
            limit=query.limit,
            cursor=query.cursor,
        )

    def get_content(self, content_id: str) -> ContentDTO | None:
        repo = ContentRepository(self.session)
        return repo.get_content(content_id)
