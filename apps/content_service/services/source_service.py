from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from apps.content_service.schemas.source import (
    HTMLSourceValidationRequest,
    RSSSourceValidationRequest,
    SourceDTO,
    SourceValidationResultDTO,
)
from apps.content_service.services.source_validation import validate_source_payload
from apps.content_service.storage.source_repository import SourceRepository


@dataclass
class SourceService:
    session: Session

    def list_sources(self, *, enabled: bool | None = None, source_type: str | None = None) -> list[SourceDTO]:
        return SourceRepository(self.session).list_sources(enabled=enabled, source_type=source_type)

    def validate_source(
        self,
        request: RSSSourceValidationRequest | HTMLSourceValidationRequest,
    ) -> SourceValidationResultDTO:
        return validate_source_payload(request)
