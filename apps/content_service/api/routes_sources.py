from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.content_service.schemas.common import DataEnvelope
from apps.content_service.schemas.source import (
    HTMLSourceValidationRequest,
    RSSSourceValidationRequest,
    SourceDTO,
    SourceValidationResultDTO,
)
from apps.content_service.services.source_service import SourceService
from apps.content_service.storage.database import get_db_session


router = APIRouter(prefix="/v1/sources", tags=["sources"])


def get_source_service(session: Session = Depends(get_db_session)) -> SourceService:
    return SourceService(session=session)


@router.get("", response_model=DataEnvelope[dict[str, list[SourceDTO]]])
def list_sources(
    enabled: bool | None = None,
    type: str | None = None,
    service: SourceService = Depends(get_source_service),
) -> DataEnvelope[dict[str, list[SourceDTO]]]:
    return DataEnvelope(data={"items": service.list_sources(enabled=enabled, source_type=type)})


@router.post("/validate", response_model=DataEnvelope[SourceValidationResultDTO])
def validate_source(
    request: RSSSourceValidationRequest | HTMLSourceValidationRequest,
    service: SourceService = Depends(get_source_service),
) -> DataEnvelope[SourceValidationResultDTO]:
    return DataEnvelope(data=service.validate_source(request))
