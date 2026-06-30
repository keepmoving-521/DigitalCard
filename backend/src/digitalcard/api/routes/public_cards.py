import hashlib
import re
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from digitalcard.core.config import Settings, get_settings
from digitalcard.core.errors import AppError
from digitalcard.core.time import utc_now
from digitalcard.db.session import get_db
from digitalcard.models.card import CardEvent, CardEventType, CardStatus, DigitalCard
from digitalcard.models.employee import Employee, EmployeeStatus
from digitalcard.models.organization import Company, CompanyStatus
from digitalcard.schemas.card import CardEventRequest, CardEventResponse, PublicCardResponse
from digitalcard.services.qr import qr_svg

router = APIRouter(prefix="/public/cards", tags=["public cards"])


def published_card(db: Session, card_id: str) -> DigitalCard:
    card = db.scalar(select(DigitalCard).where(DigitalCard.id == card_id))
    if card is None or card.published_data is None:
        raise AppError("card_not_found", "Published card was not found", 404)
    if card.status == CardStatus.OFFLINE.value:
        raise AppError("card_offline", "This card is currently offline", 410)
    if card.status != CardStatus.PUBLISHED.value:
        raise AppError("card_not_found", "Published card was not found", 404)
    employee = db.get(Employee, card.employee_id)
    if employee is None or employee.status != EmployeeStatus.ACTIVE.value:
        raise AppError("employee_inactive", "This employee card is unavailable", 410)
    company = db.get(Company, card.company_id)
    if company is None or company.status != CompanyStatus.ACTIVE.value:
        raise AppError("company_suspended", "This company card is unavailable", 410)
    if card.published_at is None:
        raise AppError("card_not_found", "Published card was not found", 404)
    return card


def canonical_share_url(settings: Settings, card_id: str, source: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]", "", source.lower())[:64] or "direct"
    return (
        f"{settings.public_card_base_url.rstrip('/')}/{card_id}?{urlencode({'source': normalized})}"
    )


@router.get("/{card_id}", response_model=PublicCardResponse, summary="Get published card")
def get_public_card(
    card_id: str,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    source: Annotated[str, Query(min_length=1, max_length=64)] = "direct",
) -> PublicCardResponse:
    card = published_card(db, card_id)
    return PublicCardResponse(
        card_id=card.id,
        employee_id=card.employee_id,
        data=card.published_data,
        published_at=card.published_at,
        share_url=canonical_share_url(settings, card.id, source),
    )


@router.get("/{card_id}/qr.svg", summary="Get card share QR code")
def get_card_qr(
    card_id: str,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    source: Annotated[str, Query(min_length=1, max_length=64)] = "qr",
) -> Response:
    card = published_card(db, card_id)
    content = canonical_share_url(settings, card.id, source)
    try:
        svg = qr_svg(content)
    except ValueError as exc:
        raise AppError("qr_content_too_long", "Share URL is too long for QR code", 422) from exc
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=300", "X-QR-Content": content},
    )


@router.post(
    "/{card_id}/events",
    response_model=CardEventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record public card event",
)
def record_card_event(
    card_id: str,
    payload: CardEventRequest,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> CardEventResponse:
    card = published_card(db, card_id)
    now = utc_now()
    visitor_hash = hashlib.sha256(payload.visitor_id.encode()).hexdigest()
    window_seconds = 1800 if payload.event_type == CardEventType.VIEW else 10
    bucket = int(now.timestamp()) // window_seconds
    dedupe_key = hashlib.sha256(
        f"{card.id}:{payload.event_type.value}:{payload.source}:{visitor_hash}:{bucket}".encode()
    ).hexdigest()
    db.add(
        CardEvent(
            card_id=card.id,
            company_id=card.company_id,
            event_type=payload.event_type.value,
            source=payload.source,
            visitor_hash=visitor_hash,
            dedupe_key=dedupe_key,
            occurred_at=now,
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        response.status_code = status.HTTP_200_OK
        return CardEventResponse(recorded=False)
    return CardEventResponse(recorded=True)
