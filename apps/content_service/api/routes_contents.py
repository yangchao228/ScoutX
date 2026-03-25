from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from apps.content_service.schemas.common import CursorList, DataEnvelope
from apps.content_service.schemas.content import ContentDTO
from apps.content_service.services.content_service import ContentQuery, ContentService
from apps.content_service.storage.database import get_db_session


router = APIRouter(prefix="/v1/contents", tags=["contents"])


def get_content_service(session: Session = Depends(get_db_session)) -> ContentService:
    return ContentService(session=session)


@router.get("", response_model=DataEnvelope[CursorList[ContentDTO]])
def list_contents(
    updated_since: str | None = None,
    published_since: str | None = None,
    source: str | None = None,
    tag: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
    service: ContentService = Depends(get_content_service),
) -> DataEnvelope[CursorList[ContentDTO]]:
    query = ContentQuery(
        updated_since=updated_since,
        published_since=published_since,
        source=source,
        tag=tag,
        limit=limit,
        cursor=cursor,
    )
    items, next_cursor = service.list_contents(query)
    return DataEnvelope(data=CursorList(items=items, next_cursor=next_cursor))


@router.get("/{content_id}", response_model=DataEnvelope[ContentDTO])
def get_content(
    content_id: str,
    service: ContentService = Depends(get_content_service),
) -> DataEnvelope[ContentDTO]:
    item = service.get_content(content_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"content {content_id} not found",
        )
    return DataEnvelope(data=item)
