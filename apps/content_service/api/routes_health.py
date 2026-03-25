from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.content_service.schemas.common import DataEnvelope
from apps.content_service.schemas.status import StatusDTO
from apps.content_service.services.status_service import StatusService
from apps.content_service.settings import load_settings
from apps.content_service.storage.database import get_db_session


router = APIRouter(tags=["health"])


@router.get("/health", response_model=DataEnvelope[dict[str, object]])
def healthcheck() -> DataEnvelope[dict[str, object]]:
    settings = load_settings()
    return DataEnvelope(
        data={
            "ok": True,
            "service": settings.app_name,
            "env": settings.app_env,
            "time": datetime.now(timezone.utc).isoformat(),
        }
    )


def get_status_service(session: Session = Depends(get_db_session)) -> StatusService:
    return StatusService(session=session)


@router.get("/v1/status", response_model=DataEnvelope[StatusDTO])
def service_status(
    service: StatusService = Depends(get_status_service),
) -> DataEnvelope[StatusDTO]:
    return DataEnvelope(data=service.get_status())
