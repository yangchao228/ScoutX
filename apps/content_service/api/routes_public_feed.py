from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.content_service.schemas.public_feed import PublicFeedDTO, PublicFeedMetaDTO
from apps.content_service.services.public_feed_service import PublicFeedService
from apps.content_service.settings import load_settings
from apps.content_service.storage.database import get_db_session


router = APIRouter(prefix="/v1/public", tags=["public-feed"])


def get_public_feed_service(session: Session = Depends(get_db_session)) -> PublicFeedService:
    return PublicFeedService(session=session, settings=load_settings())


@router.get("/meta", response_model=PublicFeedMetaDTO)
def get_public_feed_meta(
    service: PublicFeedService = Depends(get_public_feed_service),
) -> PublicFeedMetaDTO:
    return service.build_meta()


@router.get("/feed", response_model=PublicFeedDTO)
def get_public_feed(
    limit: int | None = Query(default=None, ge=1, le=200),
    hours: int | None = Query(default=None, ge=1, le=24 * 30),
    service: PublicFeedService = Depends(get_public_feed_service),
) -> PublicFeedDTO:
    resolved_limit = limit if limit is not None else service.settings.public_feed_default_limit
    resolved_hours = hours if hours is not None else service.settings.public_feed_default_hours
    return service.build_feed(limit=resolved_limit, hours=resolved_hours)
