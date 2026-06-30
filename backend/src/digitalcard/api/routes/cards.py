from copy import deepcopy
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from digitalcard.api.dependencies import require_permission
from digitalcard.core.errors import AppError
from digitalcard.core.time import utc_now
from digitalcard.db.session import get_db
from digitalcard.models.account import User
from digitalcard.models.card import (
    CardEvent,
    CardEventType,
    CardStatus,
    CardTemplate,
    DigitalCard,
)
from digitalcard.models.employee import Employee, EmployeeStatus
from digitalcard.models.organization import Company
from digitalcard.schemas.card import (
    CardAnalyticsResponse,
    CardDraftUpdateRequest,
    CardPreviewResponse,
    CardTemplateResponse,
    CardTemplateUpdateRequest,
    DigitalCardResponse,
)
from digitalcard.services.cards import (
    card_response,
    get_or_create_card,
    get_or_create_template,
    public_snapshot,
    resolve_card_data,
    validate_publishable,
)
from digitalcard.services.permissions import Permission
from digitalcard.services.tenancy import record_tenant_audit

router = APIRouter(prefix="/tenant", tags=["digital cards"])


def tenant_company(db: Session, company_id: str) -> Company:
    company = db.get(Company, company_id)
    if company is None:
        raise AppError("company_not_found", "Company was not found", 404)
    return company


def employee_for_user(db: Session, user: User) -> Employee:
    employee = db.scalar(
        select(Employee).where(Employee.company_id == user.company_id, Employee.user_id == user.id)
    )
    if employee is None:
        raise AppError("employee_profile_not_found", "Employee profile was not found", 404)
    return employee


def tenant_employee(db: Session, company_id: str, employee_id: str) -> Employee:
    employee = db.scalar(
        select(Employee).where(Employee.id == employee_id, Employee.company_id == company_id)
    )
    if employee is None:
        raise AppError("employee_not_found", "Employee was not found", 404)
    return employee


def update_card_draft(
    db: Session,
    card: DigitalCard,
    template: CardTemplate,
    payload: CardDraftUpdateRequest,
    actor: User,
    employee_edit: bool,
) -> DigitalCard:
    changes = payload.model_dump(exclude_unset=True, mode="json")
    denied = set(changes) & set(template.locked_fields)
    if employee_edit:
        denied.update(set(changes) - set(template.employee_editable_fields) - {"visible_fields"})
    if denied:
        raise AppError(
            "card_field_locked",
            "One or more card fields are controlled by the company",
            403,
            {"fields": sorted(denied)},
        )
    if changes:
        draft = dict(card.draft_data)
        draft.update(changes)
        card.draft_data = draft
        card.draft_revision += 1
        record_tenant_audit(
            db,
            card.company_id,
            actor.id,
            "card.draft_updated",
            "digital_card",
            card.id,
            {"fields": sorted(changes), "employee_id": card.employee_id},
        )
        db.commit()
        db.refresh(card)
    return card


def preview_card(db: Session, employee: Employee) -> CardPreviewResponse:
    company = tenant_company(db, employee.company_id)
    template = get_or_create_template(db, company)
    card = get_or_create_card(db, employee)
    db.commit()
    return CardPreviewResponse(
        card_id=card.id,
        status=CardStatus(card.status),
        data=resolve_card_data(company, template, card.draft_data),
        has_unpublished_changes=card.published_revision != card.draft_revision,
    )


def publish_card(db: Session, employee: Employee, actor: User) -> DigitalCard:
    if employee.status != EmployeeStatus.ACTIVE.value:
        raise AppError("employee_inactive", "Inactive employee cards cannot be published", 409)
    company = tenant_company(db, employee.company_id)
    template = get_or_create_template(db, company)
    card = get_or_create_card(db, employee)
    resolved = resolve_card_data(company, template, card.draft_data)
    validate_publishable(resolved)
    card.published_data = deepcopy(public_snapshot(resolved))
    card.published_revision = card.draft_revision
    card.status = CardStatus.PUBLISHED.value
    card.published_at = utc_now()
    card.offline_at = None
    record_tenant_audit(
        db,
        card.company_id,
        actor.id,
        "card.published",
        "digital_card",
        card.id,
        {"employee_id": employee.id, "revision": card.published_revision},
    )
    db.commit()
    db.refresh(card)
    return card


def offline_card(db: Session, employee: Employee, actor: User) -> DigitalCard:
    card = get_or_create_card(db, employee)
    if card.published_data is None:
        raise AppError("card_not_published", "Card has not been published", 409)
    card.status = CardStatus.OFFLINE.value
    card.offline_at = utc_now()
    record_tenant_audit(
        db,
        card.company_id,
        actor.id,
        "card.offline",
        "digital_card",
        card.id,
        {"employee_id": employee.id},
    )
    db.commit()
    db.refresh(card)
    return card


def card_analytics(db: Session, employee: Employee) -> CardAnalyticsResponse:
    card = get_or_create_card(db, employee)
    db.commit()
    by_event = {
        event_type: count
        for event_type, count in db.execute(
            select(CardEvent.event_type, func.count())
            .where(CardEvent.card_id == card.id)
            .group_by(CardEvent.event_type)
        )
    }
    by_source = {
        source: count
        for source, count in db.execute(
            select(CardEvent.source, func.count())
            .where(CardEvent.card_id == card.id)
            .group_by(CardEvent.source)
        )
    }
    views = by_event.get(CardEventType.VIEW.value, 0)
    return CardAnalyticsResponse(
        total_views=views,
        total_actions=sum(by_event.values()) - views,
        by_event=by_event,
        by_source=by_source,
    )


@router.get("/card-template", response_model=CardTemplateResponse, summary="Get card template")
def get_card_template(
    user: Annotated[User, Depends(require_permission(Permission.CARD_READ))],
    db: Annotated[Session, Depends(get_db)],
) -> CardTemplate:
    template = get_or_create_template(db, tenant_company(db, user.company_id))
    db.commit()
    db.refresh(template)
    return template


@router.put("/card-template", response_model=CardTemplateResponse, summary="Update card template")
def update_card_template(
    payload: CardTemplateUpdateRequest,
    user: Annotated[User, Depends(require_permission(Permission.CARD_TEMPLATE_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
) -> CardTemplate:
    template = get_or_create_template(db, tenant_company(db, user.company_id))
    changes = payload.model_dump(mode="json")
    for field, value in changes.items():
        setattr(template, field, value)
    template.revision += 1
    record_tenant_audit(
        db,
        user.company_id,
        user.id,
        "card_template.updated",
        "card_template",
        template.id,
        {"fields": sorted(changes), "revision": template.revision},
    )
    db.commit()
    db.refresh(template)
    return template


@router.get("/cards/me", response_model=DigitalCardResponse, summary="Get my card")
def get_my_card(
    user: Annotated[User, Depends(require_permission(Permission.CARD_READ))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    card = get_or_create_card(db, employee_for_user(db, user))
    db.commit()
    db.refresh(card)
    return card_response(card)


@router.patch("/cards/me", response_model=DigitalCardResponse, summary="Update my card draft")
def update_my_card(
    payload: CardDraftUpdateRequest,
    user: Annotated[User, Depends(require_permission(Permission.CARD_EDIT_SELF))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    employee = employee_for_user(db, user)
    company = tenant_company(db, user.company_id)
    card = get_or_create_card(db, employee)
    template = get_or_create_template(db, company)
    return card_response(update_card_draft(db, card, template, payload, user, True))


@router.get("/cards/me/preview", response_model=CardPreviewResponse, summary="Preview my draft")
def preview_my_card(
    user: Annotated[User, Depends(require_permission(Permission.CARD_READ))],
    db: Annotated[Session, Depends(get_db)],
) -> CardPreviewResponse:
    return preview_card(db, employee_for_user(db, user))


@router.post("/cards/me/publish", response_model=DigitalCardResponse, summary="Publish my card")
def publish_my_card(
    user: Annotated[User, Depends(require_permission(Permission.CARD_PUBLISH_SELF))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    return card_response(publish_card(db, employee_for_user(db, user), user))


@router.post(
    "/cards/me/offline", response_model=DigitalCardResponse, summary="Take my card offline"
)
def offline_my_card(
    user: Annotated[User, Depends(require_permission(Permission.CARD_PUBLISH_SELF))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    return card_response(offline_card(db, employee_for_user(db, user), user))


@router.get(
    "/cards/me/analytics", response_model=CardAnalyticsResponse, summary="Get my card analytics"
)
def get_my_card_analytics(
    user: Annotated[User, Depends(require_permission(Permission.CARD_READ))],
    db: Annotated[Session, Depends(get_db)],
) -> CardAnalyticsResponse:
    return card_analytics(db, employee_for_user(db, user))


@router.get(
    "/cards/{employee_id}/analytics",
    response_model=CardAnalyticsResponse,
    summary="Get employee card analytics",
)
def get_employee_card_analytics(
    employee_id: str,
    user: Annotated[User, Depends(require_permission(Permission.CARD_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
) -> CardAnalyticsResponse:
    return card_analytics(db, tenant_employee(db, user.company_id, employee_id))


@router.get("/cards/{employee_id}", response_model=DigitalCardResponse, summary="Get employee card")
def get_employee_card(
    employee_id: str,
    user: Annotated[User, Depends(require_permission(Permission.CARD_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    card = get_or_create_card(db, tenant_employee(db, user.company_id, employee_id))
    db.commit()
    db.refresh(card)
    return card_response(card)


@router.patch(
    "/cards/{employee_id}", response_model=DigitalCardResponse, summary="Update employee card"
)
def update_employee_card(
    employee_id: str,
    payload: CardDraftUpdateRequest,
    user: Annotated[User, Depends(require_permission(Permission.CARD_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    employee = tenant_employee(db, user.company_id, employee_id)
    company = tenant_company(db, user.company_id)
    card = get_or_create_card(db, employee)
    template = get_or_create_template(db, company)
    return card_response(update_card_draft(db, card, template, payload, user, False))


@router.get(
    "/cards/{employee_id}/preview",
    response_model=CardPreviewResponse,
    summary="Preview employee card",
)
def preview_employee_card(
    employee_id: str,
    user: Annotated[User, Depends(require_permission(Permission.CARD_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
) -> CardPreviewResponse:
    return preview_card(db, tenant_employee(db, user.company_id, employee_id))


@router.post(
    "/cards/{employee_id}/publish",
    response_model=DigitalCardResponse,
    summary="Publish employee card",
)
def publish_employee_card(
    employee_id: str,
    user: Annotated[User, Depends(require_permission(Permission.CARD_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    return card_response(publish_card(db, tenant_employee(db, user.company_id, employee_id), user))


@router.post(
    "/cards/{employee_id}/offline",
    response_model=DigitalCardResponse,
    summary="Take employee card offline",
)
def offline_employee_card(
    employee_id: str,
    user: Annotated[User, Depends(require_permission(Permission.CARD_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    return card_response(offline_card(db, tenant_employee(db, user.company_id, employee_id), user))
