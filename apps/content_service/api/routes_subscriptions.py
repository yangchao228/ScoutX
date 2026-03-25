from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from apps.content_service.schemas.common import DataEnvelope
from apps.content_service.schemas.subscription import (
    SubscriptionCreateRequest,
    SubscriptionDTO,
    SubscriptionRunDTO,
    SubscriptionUpdateRequest,
)
from apps.content_service.services.subscription_service import SubscriptionService
from apps.content_service.storage.database import get_db_session


router = APIRouter(prefix="/v1/subscriptions", tags=["subscriptions"])


def get_subscription_service(session: Session = Depends(get_db_session)) -> SubscriptionService:
    return SubscriptionService(session=session)


@router.get("", response_model=DataEnvelope[dict[str, list[SubscriptionDTO]]])
def list_subscriptions(
    service: SubscriptionService = Depends(get_subscription_service),
) -> DataEnvelope[dict[str, list[SubscriptionDTO]]]:
    return DataEnvelope(data={"items": service.list_subscriptions()})


@router.post("", response_model=DataEnvelope[SubscriptionDTO], status_code=status.HTTP_201_CREATED)
def create_subscription(
    request: SubscriptionCreateRequest,
    service: SubscriptionService = Depends(get_subscription_service),
) -> DataEnvelope[SubscriptionDTO]:
    return DataEnvelope(data=service.create_subscription(request))


@router.get("/{subscription_id}", response_model=DataEnvelope[SubscriptionDTO])
def get_subscription(
    subscription_id: str,
    service: SubscriptionService = Depends(get_subscription_service),
) -> DataEnvelope[SubscriptionDTO]:
    item = service.get_subscription(subscription_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"subscription {subscription_id} not found",
        )
    return DataEnvelope(data=item)


@router.patch("/{subscription_id}", response_model=DataEnvelope[SubscriptionDTO])
def update_subscription(
    subscription_id: str,
    request: SubscriptionUpdateRequest,
    service: SubscriptionService = Depends(get_subscription_service),
) -> DataEnvelope[SubscriptionDTO]:
    item = service.update_subscription(subscription_id, request)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"subscription {subscription_id} not found",
        )
    return DataEnvelope(data=item)


@router.post("/{subscription_id}/preview", response_model=DataEnvelope[SubscriptionRunDTO])
def preview_subscription(
    subscription_id: str,
    service: SubscriptionService = Depends(get_subscription_service),
) -> DataEnvelope[SubscriptionRunDTO]:
    item = service.preview_subscription(subscription_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"subscription {subscription_id} not found",
        )
    return DataEnvelope(data=item)


@router.post("/{subscription_id}/run", response_model=DataEnvelope[SubscriptionRunDTO])
def run_subscription(
    subscription_id: str,
    service: SubscriptionService = Depends(get_subscription_service),
) -> DataEnvelope[SubscriptionRunDTO]:
    item = service.run_subscription(subscription_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"subscription {subscription_id} not found",
        )
    return DataEnvelope(data=item)
