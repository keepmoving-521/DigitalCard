from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from digitalcard.core.errors import AppError
from digitalcard.db.session import get_db
from digitalcard.models.card import CardStatus, DigitalCard
from digitalcard.models.employee import Employee, EmployeeStatus
from digitalcard.models.organization import Company, CompanyStatus
from digitalcard.schemas.card import PublicCardResponse

router = APIRouter(prefix="/public/cards", tags=["public cards"])


@router.get("/{card_id}", response_model=PublicCardResponse, summary="Get published card")
def get_public_card(card_id: str, db: Annotated[Session, Depends(get_db)]) -> PublicCardResponse:
    card = db.scalar(select(DigitalCard).where(DigitalCard.id == card_id))
    if card is None or card.status != CardStatus.PUBLISHED.value or card.published_data is None:
        raise AppError("card_not_found", "Published card was not found", 404)
    employee = db.get(Employee, card.employee_id)
    company = db.get(Company, card.company_id)
    if (
        employee is None
        or employee.status != EmployeeStatus.ACTIVE.value
        or company is None
        or company.status != CompanyStatus.ACTIVE.value
        or card.published_at is None
    ):
        raise AppError("card_not_found", "Published card was not found", 404)
    return PublicCardResponse(
        card_id=card.id,
        employee_id=card.employee_id,
        data=card.published_data,
        published_at=card.published_at,
    )
