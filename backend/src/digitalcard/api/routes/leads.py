import re
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from digitalcard.api.dependencies import require_permission
from digitalcard.api.routes.public_cards import published_card
from digitalcard.core.errors import AppError
from digitalcard.core.time import utc_now
from digitalcard.db.session import get_db
from digitalcard.models.account import User, UserRole
from digitalcard.models.employee import Employee, EmployeeStatus
from digitalcard.models.lead import Lead, LeadStatus, Notification
from digitalcard.models.product import Product, ProductStatus
from digitalcard.schemas.lead import (
    LeadAssignRequest,
    LeadPageResponse,
    LeadResponse,
    LeadStatusRequest,
    NotificationPageResponse,
    PublicLeadCreateRequest,
    PublicLeadCreateResponse,
)
from digitalcard.services.permissions import Permission, permissions_for_user
from digitalcard.services.tenancy import record_tenant_audit

router = APIRouter(tags=["leads"])


def normalized_contact(value: str) -> str:
    if "@" in value:
        return value.strip().lower()
    return re.sub(r"\D", "", value)


def current_employee(db: Session, user: User) -> Employee | None:
    return db.scalar(
        select(Employee).where(Employee.user_id == user.id, Employee.company_id == user.company_id)
    )


def can_manage_leads(db: Session, user: User) -> bool:
    return Permission.LEAD_MANAGE.value in permissions_for_user(db, user)


def visible_lead(db: Session, user: User, lead_id: str) -> Lead:
    lead = db.scalar(select(Lead).where(Lead.id == lead_id, Lead.company_id == user.company_id))
    if lead is None:
        raise AppError("lead_not_found", "Lead was not found", 404)
    if not can_manage_leads(db, user):
        employee = current_employee(db, user)
        if employee is None or lead.assigned_employee_id != employee.id:
            raise AppError("lead_not_found", "Lead was not found", 404)
    return lead


def notify_user(db: Session, user_id: str | None, company_id: str, lead: Lead, title: str) -> None:
    if not user_id:
        return
    db.add(
        Notification(
            company_id=company_id,
            user_id=user_id,
            kind="lead",
            title=title,
            content=f"{lead.name} 提交了新的咨询信息",
            related_type="lead",
            related_id=lead.id,
        )
    )


@router.post(
    "/public/cards/{card_id}/leads",
    response_model=PublicLeadCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a public card inquiry",
)
def create_public_lead(
    card_id: str,
    payload: PublicLeadCreateRequest,
    db: Annotated[Session, Depends(get_db)],
) -> PublicLeadCreateResponse:
    card = published_card(db, card_id)
    if payload.product_id:
        product = db.scalar(
            select(Product).where(
                Product.id == payload.product_id,
                Product.company_id == card.company_id,
                Product.status == ProductStatus.PUBLISHED.value,
            )
        )
        recommended = card.published_data.get("recommended_product_ids", [])
        if product is None or product.id not in recommended:
            raise AppError("lead_product_unavailable", "Selected product is unavailable", 422)
    contact = normalized_contact(payload.contact)
    now = utc_now()
    duplicate = db.scalar(
        select(Lead)
        .where(
            Lead.company_id == card.company_id,
            Lead.card_id == card.id,
            Lead.normalized_contact == contact,
            Lead.last_submitted_at >= now - timedelta(hours=24),
        )
        .order_by(Lead.last_submitted_at.desc())
    )
    if duplicate:
        duplicate.duplicate_count += 1
        duplicate.last_submitted_at = now
        duplicate.demand = payload.demand or duplicate.demand
        duplicate.product_id = payload.product_id or duplicate.product_id
        duplicate.source = payload.source
        db.commit()
        return PublicLeadCreateResponse(
            id=duplicate.id, duplicate=True, message="已收到相同联系方式的咨询，请勿重复提交"
        )
    owner = db.get(Employee, card.employee_id)
    if owner is None or owner.status != EmployeeStatus.ACTIVE.value:
        raise AppError("employee_inactive", "This employee card is unavailable", 410)
    lead = Lead(
        company_id=card.company_id,
        card_id=card.id,
        product_id=payload.product_id,
        owner_employee_id=owner.id,
        assigned_employee_id=owner.id,
        name=payload.name,
        contact=payload.contact,
        normalized_contact=contact,
        demand=payload.demand,
        source=payload.source,
        privacy_agreed=True,
        status=LeadStatus.ASSIGNED.value,
    )
    db.add(lead)
    db.flush()
    notify_user(db, owner.user_id, card.company_id, lead, "收到新线索")
    admins = db.scalars(
        select(User).where(
            User.company_id == card.company_id,
            User.role == UserRole.COMPANY_ADMIN.value,
            User.is_active.is_(True),
            User.id != owner.user_id,
        )
    )
    for admin in admins:
        notify_user(db, admin.id, card.company_id, lead, "企业收到新线索")
    db.commit()
    return PublicLeadCreateResponse(id=lead.id, duplicate=False, message="咨询已提交")


@router.get("/tenant/leads", response_model=LeadPageResponse, summary="List visible leads")
def list_leads(
    user: Annotated[User, Depends(require_permission(Permission.LEAD_READ))],
    db: Annotated[Session, Depends(get_db)],
    lead_status: Annotated[LeadStatus | None, Query(alias="status")] = None,
    search: Annotated[str | None, Query(max_length=100)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> LeadPageResponse:
    conditions = [Lead.company_id == user.company_id]
    if not can_manage_leads(db, user):
        employee = current_employee(db, user)
        conditions.append(Lead.assigned_employee_id == (employee.id if employee else ""))
    if lead_status:
        conditions.append(Lead.status == lead_status.value)
    if search:
        pattern = f"%{search.strip()}%"
        conditions.append(or_(Lead.name.ilike(pattern), Lead.contact.ilike(pattern)))
    total = db.scalar(select(func.count()).select_from(Lead).where(*conditions)) or 0
    items = list(
        db.scalars(
            select(Lead)
            .where(*conditions)
            .order_by(Lead.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    )
    return LeadPageResponse(items=items, total=total, offset=offset, limit=limit)


@router.get("/tenant/leads/{lead_id}", response_model=LeadResponse, summary="Get lead")
def get_lead(
    lead_id: str,
    user: Annotated[User, Depends(require_permission(Permission.LEAD_READ))],
    db: Annotated[Session, Depends(get_db)],
) -> Lead:
    return visible_lead(db, user, lead_id)


@router.post("/tenant/leads/{lead_id}/assign", response_model=LeadResponse)
def assign_lead(
    lead_id: str,
    payload: LeadAssignRequest,
    user: Annotated[User, Depends(require_permission(Permission.LEAD_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
) -> Lead:
    lead = visible_lead(db, user, lead_id)
    employee = db.scalar(
        select(Employee).where(
            Employee.id == payload.employee_id,
            Employee.company_id == user.company_id,
            Employee.status == EmployeeStatus.ACTIVE.value,
        )
    )
    if employee is None:
        raise AppError("employee_not_found", "Active employee was not found", 404)
    lead.assigned_employee_id = employee.id
    lead.status = LeadStatus.ASSIGNED.value
    lead.claimed_at = None
    notify_user(db, employee.user_id, lead.company_id, lead, "有一条线索分配给你")
    record_tenant_audit(
        db,
        lead.company_id,
        user.id,
        "lead.assigned",
        "lead",
        lead.id,
        {"employee_id": employee.id},
    )
    db.commit()
    db.refresh(lead)
    return lead


@router.post("/tenant/leads/{lead_id}/claim", response_model=LeadResponse)
def claim_lead(
    lead_id: str,
    user: Annotated[User, Depends(require_permission(Permission.LEAD_CLAIM))],
    db: Annotated[Session, Depends(get_db)],
) -> Lead:
    lead = visible_lead(db, user, lead_id)
    employee = current_employee(db, user)
    if employee is None or lead.assigned_employee_id != employee.id:
        raise AppError("lead_not_assigned", "Lead is not assigned to current employee", 409)
    if lead.status == LeadStatus.INVALID.value:
        raise AppError("lead_invalid", "Invalid lead cannot be claimed", 409)
    lead.status = LeadStatus.CLAIMED.value
    lead.claimed_at = utc_now()
    db.commit()
    db.refresh(lead)
    return lead


@router.post("/tenant/leads/{lead_id}/status", response_model=LeadResponse)
def update_lead_status(
    lead_id: str,
    payload: LeadStatusRequest,
    user: Annotated[User, Depends(require_permission(Permission.LEAD_READ))],
    db: Annotated[Session, Depends(get_db)],
) -> Lead:
    lead = visible_lead(db, user, lead_id)
    if not can_manage_leads(db, user) and Permission.LEAD_CLAIM.value not in permissions_for_user(
        db, user
    ):
        raise AppError("permission_denied", "Permission is required", 403)
    lead.status = payload.status.value
    db.commit()
    db.refresh(lead)
    return lead


@router.get("/tenant/notifications", response_model=NotificationPageResponse)
def list_notifications(
    user: Annotated[User, Depends(require_permission(Permission.NOTIFICATION_READ))],
    db: Annotated[Session, Depends(get_db)],
    unread_only: bool = False,
) -> NotificationPageResponse:
    conditions = [Notification.user_id == user.id, Notification.company_id == user.company_id]
    unread_count = (
        db.scalar(
            select(func.count())
            .select_from(Notification)
            .where(*conditions, Notification.read_at.is_(None))
        )
        or 0
    )
    if unread_only:
        conditions.append(Notification.read_at.is_(None))
    items = list(
        db.scalars(
            select(Notification)
            .where(*conditions)
            .order_by(Notification.created_at.desc())
            .limit(50)
        )
    )
    return NotificationPageResponse(items=items, unread_count=unread_count)


@router.post("/tenant/notifications/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def read_notification(
    notification_id: str,
    user: Annotated[User, Depends(require_permission(Permission.NOTIFICATION_READ))],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    notification = db.scalar(
        select(Notification).where(
            Notification.id == notification_id, Notification.user_id == user.id
        )
    )
    if notification is None:
        raise AppError("notification_not_found", "Notification was not found", 404)
    notification.read_at = utc_now()
    db.commit()
