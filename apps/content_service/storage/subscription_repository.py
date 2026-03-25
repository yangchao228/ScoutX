from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import uuid

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from apps.content_service.schemas.subscription import (
    SubscriptionDTO,
    SubscriptionFiltersDTO,
    SubscriptionRunDTO,
)
from apps.content_service.storage.models import DeliveryRunRecord, SubscriptionRecord


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _format_rfc3339(value: datetime | None) -> str | None:
    if value is None:
        return None
    dt = value.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def _subscription_id() -> str:
    return f"sub_{uuid.uuid4().hex[:12]}"


def _run_id() -> str:
    return f"run_{uuid.uuid4().hex[:12]}"


def _filters_from_record(record: SubscriptionRecord) -> SubscriptionFiltersDTO:
    payload = dict(record.filters or {})
    known = {
        "sources": list(payload.pop("sources", []) or []),
        "tags": list(payload.pop("tags", []) or []),
        "keywords_allow": list(payload.pop("keywords_allow", []) or []),
        "keywords_deny": list(payload.pop("keywords_deny", []) or []),
        "published_within_hours": payload.pop("published_within_hours", None),
        "max_items": payload.pop("max_items", None),
        "extra": payload,
    }
    return SubscriptionFiltersDTO.model_validate(known)


def _to_subscription_dto(record: SubscriptionRecord) -> SubscriptionDTO:
    return SubscriptionDTO(
        subscription_id=record.subscription_id,
        name=record.name,
        enabled=record.enabled,
        timezone=record.timezone,
        cadence=record.cadence,
        delivery_channel=record.delivery_channel,
        language=record.language,
        filters=_filters_from_record(record),
        last_cursor=record.last_cursor,
        last_run_at=_format_rfc3339(record.last_run_at),
        created_at=_format_rfc3339(record.created_at) or "",
        updated_at=_format_rfc3339(record.updated_at) or "",
    )


def _to_run_dto(record: DeliveryRunRecord) -> SubscriptionRunDTO:
    return SubscriptionRunDTO(
        run_id=record.run_id,
        subscription_id=record.subscription_id,
        status=record.status,
        delivered_count=record.delivered_count,
        started_at=_format_rfc3339(record.started_at) or "",
        completed_at=_format_rfc3339(record.completed_at),
    )


@dataclass
class SubscriptionRepository:
    session: Session

    def list_subscriptions(self) -> list[SubscriptionDTO]:
        stmt: Select[tuple[SubscriptionRecord]] = select(SubscriptionRecord).order_by(
            SubscriptionRecord.created_at.asc(),
            SubscriptionRecord.subscription_id.asc(),
        )
        rows = list(self.session.execute(stmt).scalars().all())
        return [_to_subscription_dto(row) for row in rows]

    def get_subscription(self, subscription_id: str) -> SubscriptionDTO | None:
        row = self.session.get(SubscriptionRecord, subscription_id)
        if row is None:
            return None
        return _to_subscription_dto(row)

    def create_subscription(
        self,
        *,
        name: str,
        timezone_name: str,
        cadence: str,
        delivery_channel: str,
        language: str,
        filters: dict[str, object],
    ) -> SubscriptionDTO:
        now = _utcnow()
        row = SubscriptionRecord(
            subscription_id=_subscription_id(),
            name=name,
            enabled=True,
            timezone=timezone_name,
            cadence=cadence,
            delivery_channel=delivery_channel,
            language=language,
            filters=filters,
            created_at=now,
            updated_at=now,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return _to_subscription_dto(row)

    def update_subscription(self, subscription_id: str, *, changes: dict[str, object]) -> SubscriptionDTO | None:
        row = self.session.get(SubscriptionRecord, subscription_id)
        if row is None:
            return None
        for key, value in changes.items():
            setattr(row, key, value)
        row.updated_at = _utcnow()
        self.session.commit()
        self.session.refresh(row)
        return _to_subscription_dto(row)

    def create_delivery_run(self, subscription_id: str, *, status: str) -> SubscriptionRunDTO:
        now = _utcnow()
        row = DeliveryRunRecord(
            run_id=_run_id(),
            subscription_id=subscription_id,
            status=status,
            delivered_count=0,
            started_at=now,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return _to_run_dto(row)

    def complete_delivery_run(
        self,
        run_id: str,
        *,
        status: str,
        delivered_count: int,
    ) -> SubscriptionRunDTO:
        row = self.session.get(DeliveryRunRecord, run_id)
        if row is None:
            raise ValueError(f"run {run_id} not found")
        row.status = status
        row.delivered_count = delivered_count
        row.completed_at = _utcnow()
        self.session.commit()
        self.session.refresh(row)
        return _to_run_dto(row)
