from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from digitalcard.api.dependencies import require_permission
from digitalcard.api.routes.leads import current_employee, visible_lead
from digitalcard.core.config import Settings, get_settings
from digitalcard.core.errors import AppError
from digitalcard.core.time import utc_now
from digitalcard.db.session import get_db
from digitalcard.models.account import User
from digitalcard.models.crm import (
    Customer,
    CustomerContact,
    CustomerEvent,
    CustomerStatus,
    FollowUp,
    Opportunity,
    OpportunityStage,
    OpportunityStageHistory,
)
from digitalcard.models.employee import Employee, EmployeeStatus
from digitalcard.models.lead import Lead, LeadStatus
from digitalcard.schemas.crm import (
    ContactCreateRequest,
    ContactResponse,
    ContactUpdateRequest,
    CustomerDetailResponse,
    CustomerPageResponse,
    CustomerResponse,
    CustomerTransferRequest,
    CustomerUpdateRequest,
    FollowUpCreateRequest,
    FollowUpResponse,
    FunnelItem,
    FunnelResponse,
    LeadConvertRequest,
    MergePreviewResponse,
    MergeRequest,
    OpportunityCreateRequest,
    OpportunityResponse,
    OpportunityUpdateRequest,
    StageCreateRequest,
    StageHistoryResponse,
    StageResponse,
    StageUpdateRequest,
    TimelineEventResponse,
)
from digitalcard.services.analytics import add_business_event
from digitalcard.services.open_platform import enqueue_webhooks
from digitalcard.services.permissions import Permission, permissions_for_user
from digitalcard.services.tenancy import record_tenant_audit

router = APIRouter(tags=["crm"])


def can_manage_all(db: Session, user: User) -> bool:
    return Permission.CUSTOMER_ALL_MANAGE.value in permissions_for_user(db, user)


def visible_customer(db: Session, user: User, customer_id: str, edit: bool = False) -> Customer:
    customer = db.scalar(
        select(Customer).where(Customer.id == customer_id, Customer.company_id == user.company_id)
    )
    if customer is None or customer.status == CustomerStatus.MERGED.value:
        raise AppError("customer_not_found", "Customer was not found", 404)
    permissions = permissions_for_user(db, user)
    if can_manage_all(db, user):
        return customer
    employee = current_employee(db, user)
    if employee is None or customer.owner_employee_id != employee.id:
        raise AppError("customer_not_found", "Customer was not found", 404)
    if edit and Permission.CUSTOMER_SELF_MANAGE.value not in permissions:
        raise AppError("permission_denied", "Permission is required", 403)
    return customer


def active_employee(db: Session, company_id: str, employee_id: str) -> Employee:
    employee = db.scalar(
        select(Employee).where(
            Employee.id == employee_id,
            Employee.company_id == company_id,
            Employee.status == EmployeeStatus.ACTIVE.value,
        )
    )
    if employee is None:
        raise AppError("employee_not_found", "Active employee was not found", 404)
    return employee


def add_event(
    db: Session,
    customer: Customer,
    event_type: str,
    title: str,
    actor_id: str | None,
    details: dict[str, object] | None = None,
) -> None:
    db.add(
        CustomerEvent(
            company_id=customer.company_id,
            customer_id=customer.id,
            event_type=event_type,
            title=title,
            actor_user_id=actor_id,
            details=details or {},
        )
    )


@router.post(
    "/tenant/leads/{lead_id}/convert",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
)
def convert_lead(
    lead_id: str,
    payload: LeadConvertRequest,
    user: Annotated[User, Depends(require_permission(Permission.LEAD_READ))],
    db: Annotated[Session, Depends(get_db)],
) -> Customer:
    lead = visible_lead(db, user, lead_id)
    if lead.converted_customer_id:
        raise AppError("lead_already_converted", "Lead has already been converted", 409)
    if lead.status == LeadStatus.INVALID.value:
        raise AppError("lead_invalid", "Invalid lead cannot be converted", 409)
    owner_id = payload.owner_employee_id or lead.assigned_employee_id or lead.owner_employee_id
    if payload.owner_employee_id and not can_manage_all(db, user):
        raise AppError("permission_denied", "Only administrators can select an owner", 403)
    owner = active_employee(db, lead.company_id, owner_id)
    customer = Customer(
        company_id=lead.company_id,
        owner_employee_id=owner_id,
        name=payload.name or lead.name,
        primary_contact=lead.contact,
        tags=payload.tags,
    )
    db.add(customer)
    db.flush()
    contact_type = "email" if "@" in lead.contact else "phone"
    db.add(
        CustomerContact(
            company_id=lead.company_id,
            customer_id=customer.id,
            name=lead.name,
            contact_type=contact_type,
            contact_value=lead.contact,
            is_primary=True,
        )
    )
    lead.converted_customer_id = customer.id
    lead.status = LeadStatus.CONVERTED.value
    add_business_event(
        db,
        company_id=lead.company_id,
        employee=owner,
        card_id=lead.card_id,
        product_id=lead.product_id,
        lead_id=lead.id,
        customer_id=customer.id,
        event_type="lead_converted",
        category="conversion",
        channel=lead.source,
        dedupe_key=f"lead:{lead.id}:converted",
        details={"customer_id": customer.id},
    )
    add_event(
        db,
        customer,
        "lead_converted",
        "线索转为客户",
        user.id,
        {
            "lead_id": lead.id,
            "card_id": lead.card_id,
            "product_id": lead.product_id,
            "source": lead.source,
            "submitted_at": lead.created_at.isoformat(),
        },
    )
    add_event(
        db,
        customer,
        "source_visit",
        "来源与名片访问",
        None,
        {"card_id": lead.card_id, "source": lead.source},
    )
    db.commit()
    db.refresh(customer)
    return customer


@router.get("/tenant/customers", response_model=CustomerPageResponse)
def list_customers(
    user: Annotated[User, Depends(require_permission(Permission.CUSTOMER_READ))],
    db: Annotated[Session, Depends(get_db)],
    search: Annotated[str | None, Query(max_length=100)] = None,
    include_archived: bool = False,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> CustomerPageResponse:
    conditions = [
        Customer.company_id == user.company_id,
        Customer.status != CustomerStatus.MERGED.value,
    ]
    if not can_manage_all(db, user):
        employee = current_employee(db, user)
        conditions.append(Customer.owner_employee_id == (employee.id if employee else ""))
    if not include_archived:
        conditions.append(Customer.status == CustomerStatus.ACTIVE.value)
    if search:
        pattern = f"%{search.strip()}%"
        conditions.append(
            or_(Customer.name.ilike(pattern), Customer.primary_contact.ilike(pattern))
        )
    total = db.scalar(select(func.count()).select_from(Customer).where(*conditions)) or 0
    items = list(
        db.scalars(
            select(Customer)
            .where(*conditions)
            .order_by(Customer.updated_at.desc())
            .offset(offset)
            .limit(limit)
        )
    )
    return CustomerPageResponse(items=items, total=total, offset=offset, limit=limit)


@router.get("/tenant/customers/{customer_id}", response_model=CustomerDetailResponse)
def get_customer(
    customer_id: str,
    user: Annotated[User, Depends(require_permission(Permission.CUSTOMER_READ))],
    db: Annotated[Session, Depends(get_db)],
) -> CustomerDetailResponse:
    customer = visible_customer(db, user, customer_id)
    contacts = list(
        db.scalars(
            select(CustomerContact)
            .where(CustomerContact.customer_id == customer.id)
            .order_by(CustomerContact.sort_order, CustomerContact.created_at)
        )
    )
    return CustomerDetailResponse(
        **CustomerResponse.model_validate(customer).model_dump(), contacts=contacts
    )


@router.patch("/tenant/customers/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: str,
    payload: CustomerUpdateRequest,
    user: Annotated[User, Depends(require_permission(Permission.CUSTOMER_READ))],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Customer:
    customer = visible_customer(db, user, customer_id, True)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(customer, field, value)
    enqueue_webhooks(
        db,
        settings,
        customer.company_id,
        "customer.updated",
        customer.id,
        {"customer_id": customer.id},
    )
    db.commit()
    db.refresh(customer)
    return customer


@router.post(
    "/tenant/customers/{customer_id}/contacts",
    response_model=ContactResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_contact(
    customer_id: str,
    payload: ContactCreateRequest,
    user: Annotated[User, Depends(require_permission(Permission.CUSTOMER_READ))],
    db: Annotated[Session, Depends(get_db)],
) -> CustomerContact:
    customer = visible_customer(db, user, customer_id, True)
    if payload.is_primary:
        db.execute(
            update(CustomerContact)
            .where(CustomerContact.customer_id == customer.id)
            .values(is_primary=False)
        )
        customer.primary_contact = payload.contact_value
    contact = CustomerContact(
        company_id=customer.company_id, customer_id=customer.id, **payload.model_dump()
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


def tenant_contact(db: Session, customer: Customer, contact_id: str) -> CustomerContact:
    contact = db.scalar(
        select(CustomerContact).where(
            CustomerContact.id == contact_id,
            CustomerContact.customer_id == customer.id,
            CustomerContact.company_id == customer.company_id,
        )
    )
    if contact is None:
        raise AppError("customer_contact_not_found", "Customer contact was not found", 404)
    return contact


@router.patch(
    "/tenant/customers/{customer_id}/contacts/{contact_id}",
    response_model=ContactResponse,
)
def update_contact(
    customer_id: str,
    contact_id: str,
    payload: ContactUpdateRequest,
    user: Annotated[User, Depends(require_permission(Permission.CUSTOMER_READ))],
    db: Annotated[Session, Depends(get_db)],
) -> CustomerContact:
    customer = visible_customer(db, user, customer_id, True)
    contact = tenant_contact(db, customer, contact_id)
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("is_primary"):
        db.execute(
            update(CustomerContact)
            .where(CustomerContact.customer_id == customer.id)
            .values(is_primary=False)
        )
        customer.primary_contact = str(changes.get("contact_value", contact.contact_value))
    for field, value in changes.items():
        setattr(contact, field, value)
    db.commit()
    db.refresh(contact)
    return contact


@router.delete(
    "/tenant/customers/{customer_id}/contacts/{contact_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_contact(
    customer_id: str,
    contact_id: str,
    user: Annotated[User, Depends(require_permission(Permission.CUSTOMER_READ))],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    customer = visible_customer(db, user, customer_id, True)
    contact = tenant_contact(db, customer, contact_id)
    if contact.is_primary:
        raise AppError(
            "primary_contact_delete_forbidden",
            "Primary contact cannot be deleted before selecting another primary contact",
            409,
        )
    db.delete(contact)
    db.commit()


@router.post("/tenant/customers/{customer_id}/transfer", response_model=CustomerResponse)
def transfer_customer(
    customer_id: str,
    payload: CustomerTransferRequest,
    user: Annotated[User, Depends(require_permission(Permission.CUSTOMER_ALL_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
) -> Customer:
    customer = visible_customer(db, user, customer_id)
    employee = active_employee(db, customer.company_id, payload.employee_id)
    previous = customer.owner_employee_id
    customer.owner_employee_id = employee.id
    db.execute(
        update(Opportunity)
        .where(Opportunity.customer_id == customer.id)
        .values(owner_employee_id=employee.id)
    )
    add_event(
        db,
        customer,
        "owner_transferred",
        "客户负责人变更",
        user.id,
        {"from": previous, "to": employee.id},
    )
    record_tenant_audit(
        db,
        customer.company_id,
        user.id,
        "customer.transferred",
        "customer",
        customer.id,
        {"from": previous, "to": employee.id},
    )
    db.commit()
    db.refresh(customer)
    return customer


@router.post("/tenant/customers/{customer_id}/archive", response_model=CustomerResponse)
def archive_customer(
    customer_id: str,
    user: Annotated[User, Depends(require_permission(Permission.CUSTOMER_READ))],
    db: Annotated[Session, Depends(get_db)],
) -> Customer:
    customer = visible_customer(db, user, customer_id, True)
    customer.status = CustomerStatus.ARCHIVED.value
    customer.archived_at = utc_now()
    add_event(db, customer, "archived", "客户已归档", user.id)
    db.commit()
    db.refresh(customer)
    return customer


@router.post(
    "/tenant/customers/{customer_id}/follow-ups", response_model=FollowUpResponse, status_code=201
)
def create_follow_up(
    customer_id: str,
    payload: FollowUpCreateRequest,
    user: Annotated[User, Depends(require_permission(Permission.CUSTOMER_READ))],
    db: Annotated[Session, Depends(get_db)],
) -> FollowUp:
    customer = visible_customer(db, user, customer_id, True)
    follow_up = FollowUp(
        company_id=customer.company_id,
        customer_id=customer.id,
        created_by_user_id=user.id,
        method=payload.method,
        content=payload.content,
        occurred_at=payload.occurred_at or utc_now(),
        next_follow_up_at=payload.next_follow_up_at,
    )
    db.add(follow_up)
    add_event(
        db,
        customer,
        "follow_up",
        "新增跟进记录",
        user.id,
        {
            "method": payload.method,
            "content": payload.content,
            "next_follow_up_at": payload.next_follow_up_at.isoformat()
            if payload.next_follow_up_at
            else None,
        },
    )
    db.commit()
    db.refresh(follow_up)
    return follow_up


@router.get("/tenant/customers/{customer_id}/follow-ups", response_model=list[FollowUpResponse])
def list_follow_ups(
    customer_id: str,
    user: Annotated[User, Depends(require_permission(Permission.CUSTOMER_READ))],
    db: Annotated[Session, Depends(get_db)],
) -> list[FollowUp]:
    customer = visible_customer(db, user, customer_id)
    return list(
        db.scalars(
            select(FollowUp)
            .where(FollowUp.customer_id == customer.id)
            .order_by(FollowUp.occurred_at.desc())
        )
    )


@router.get("/tenant/customers/{customer_id}/timeline", response_model=list[TimelineEventResponse])
def customer_timeline(
    customer_id: str,
    user: Annotated[User, Depends(require_permission(Permission.CUSTOMER_READ))],
    db: Annotated[Session, Depends(get_db)],
) -> list[CustomerEvent]:
    customer = visible_customer(db, user, customer_id)
    return list(
        db.scalars(
            select(CustomerEvent)
            .where(CustomerEvent.customer_id == customer.id)
            .order_by(CustomerEvent.occurred_at.desc())
        )
    )


def merge_preview_data(db: Session, target: Customer, source: Customer) -> MergePreviewResponse:
    contacts = (
        db.scalar(
            select(func.count())
            .select_from(CustomerContact)
            .where(CustomerContact.customer_id == source.id)
        )
        or 0
    )
    follow_ups = (
        db.scalar(
            select(func.count()).select_from(FollowUp).where(FollowUp.customer_id == source.id)
        )
        or 0
    )
    opportunities = (
        db.scalar(
            select(func.count())
            .select_from(Opportunity)
            .where(Opportunity.customer_id == source.id)
        )
        or 0
    )
    conflicts: dict[str, list[str]] = {}
    if target.name != source.name:
        conflicts["name"] = [target.name, source.name]
    if target.primary_contact != source.primary_contact:
        conflicts["primary_contact"] = [target.primary_contact, source.primary_contact]
    return MergePreviewResponse(
        target_customer_id=target.id,
        source_customer_id=source.id,
        conflicts=conflicts,
        moved_counts={
            "contacts": contacts,
            "follow_ups": follow_ups,
            "opportunities": opportunities,
        },
    )


@router.post("/tenant/customers/{customer_id}/merge-preview", response_model=MergePreviewResponse)
def preview_merge(
    customer_id: str,
    payload: MergeRequest,
    user: Annotated[User, Depends(require_permission(Permission.CUSTOMER_ALL_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
) -> MergePreviewResponse:
    target = visible_customer(db, user, customer_id)
    source = visible_customer(db, user, payload.source_customer_id)
    if target.id == source.id:
        raise AppError("customer_merge_same", "A customer cannot be merged into itself", 422)
    return merge_preview_data(db, target, source)


@router.post("/tenant/customers/{customer_id}/merge", response_model=CustomerResponse)
def merge_customers(
    customer_id: str,
    payload: MergeRequest,
    user: Annotated[User, Depends(require_permission(Permission.CUSTOMER_ALL_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
) -> Customer:
    target = visible_customer(db, user, customer_id)
    source = visible_customer(db, user, payload.source_customer_id)
    if target.id == source.id:
        raise AppError("customer_merge_same", "A customer cannot be merged into itself", 422)
    for model in (CustomerContact, FollowUp, CustomerEvent, Opportunity):
        db.execute(
            update(model).where(model.customer_id == source.id).values(customer_id=target.id)
        )
    db.execute(
        update(Lead)
        .where(Lead.converted_customer_id == source.id)
        .values(converted_customer_id=target.id)
    )
    target.tags = list(dict.fromkeys([*target.tags, *source.tags]))
    source.status = CustomerStatus.MERGED.value
    source.merged_into_id = target.id
    add_event(db, target, "merged", "合并客户档案", user.id, {"source_customer_id": source.id})
    db.commit()
    db.refresh(target)
    return target


@router.get("/tenant/opportunity-stages", response_model=list[StageResponse])
def list_stages(
    user: Annotated[User, Depends(require_permission(Permission.CUSTOMER_READ))],
    db: Annotated[Session, Depends(get_db)],
) -> list[OpportunityStage]:
    return list(
        db.scalars(
            select(OpportunityStage)
            .where(OpportunityStage.company_id == user.company_id)
            .order_by(OpportunityStage.sort_order)
        )
    )


@router.post("/tenant/opportunity-stages", response_model=StageResponse, status_code=201)
def create_stage(
    payload: StageCreateRequest,
    user: Annotated[User, Depends(require_permission(Permission.OPPORTUNITY_STAGE_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
) -> OpportunityStage:
    if payload.is_won and payload.is_lost:
        raise AppError("invalid_stage", "A stage cannot be both won and lost", 422)
    if db.scalar(
        select(OpportunityStage.id).where(
            OpportunityStage.company_id == user.company_id,
            OpportunityStage.code == payload.code,
        )
    ):
        raise AppError("opportunity_stage_code_exists", "Opportunity stage code exists", 409)
    stage = OpportunityStage(company_id=user.company_id, **payload.model_dump())
    db.add(stage)
    db.commit()
    db.refresh(stage)
    return stage


@router.patch("/tenant/opportunity-stages/{stage_id}", response_model=StageResponse)
def update_stage(
    stage_id: str,
    payload: StageUpdateRequest,
    user: Annotated[User, Depends(require_permission(Permission.OPPORTUNITY_STAGE_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
) -> OpportunityStage:
    stage = db.scalar(
        select(OpportunityStage).where(
            OpportunityStage.id == stage_id, OpportunityStage.company_id == user.company_id
        )
    )
    if stage is None:
        raise AppError("opportunity_stage_not_found", "Opportunity stage was not found", 404)
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("is_won", stage.is_won) and changes.get("is_lost", stage.is_lost):
        raise AppError("invalid_stage", "A stage cannot be both won and lost", 422)
    for field, value in changes.items():
        setattr(stage, field, value)
    db.commit()
    db.refresh(stage)
    return stage


def tenant_stage(db: Session, company_id: str, stage_id: str) -> OpportunityStage:
    stage = db.scalar(
        select(OpportunityStage).where(
            OpportunityStage.id == stage_id,
            OpportunityStage.company_id == company_id,
            OpportunityStage.is_active.is_(True),
        )
    )
    if stage is None:
        raise AppError("opportunity_stage_not_found", "Active opportunity stage was not found", 404)
    return stage


@router.post(
    "/tenant/customers/{customer_id}/opportunities",
    response_model=OpportunityResponse,
    status_code=201,
)
def create_opportunity(
    customer_id: str,
    payload: OpportunityCreateRequest,
    user: Annotated[User, Depends(require_permission(Permission.OPPORTUNITY_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
) -> Opportunity:
    customer = visible_customer(db, user, customer_id, True)
    stage = tenant_stage(db, customer.company_id, payload.stage_id)
    opportunity = Opportunity(
        company_id=customer.company_id,
        customer_id=customer.id,
        owner_employee_id=customer.owner_employee_id,
        **payload.model_dump(),
    )
    db.add(opportunity)
    db.flush()
    db.add(
        OpportunityStageHistory(
            opportunity_id=opportunity.id,
            from_stage_id=None,
            to_stage_id=stage.id,
            actor_user_id=user.id,
        )
    )
    add_event(
        db,
        customer,
        "opportunity_created",
        "创建商机",
        user.id,
        {
            "opportunity_id": opportunity.id,
            "stage_id": stage.id,
            "amount": str(opportunity.expected_amount),
        },
    )
    db.commit()
    db.refresh(opportunity)
    return opportunity


@router.get(
    "/tenant/customers/{customer_id}/opportunities", response_model=list[OpportunityResponse]
)
def list_opportunities(
    customer_id: str,
    user: Annotated[User, Depends(require_permission(Permission.CUSTOMER_READ))],
    db: Annotated[Session, Depends(get_db)],
) -> list[Opportunity]:
    customer = visible_customer(db, user, customer_id)
    return list(
        db.scalars(
            select(Opportunity)
            .where(Opportunity.customer_id == customer.id)
            .order_by(Opportunity.updated_at.desc())
        )
    )


@router.patch("/tenant/opportunities/{opportunity_id}", response_model=OpportunityResponse)
def update_opportunity(
    opportunity_id: str,
    payload: OpportunityUpdateRequest,
    user: Annotated[User, Depends(require_permission(Permission.OPPORTUNITY_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
) -> Opportunity:
    opportunity = db.scalar(
        select(Opportunity).where(
            Opportunity.id == opportunity_id, Opportunity.company_id == user.company_id
        )
    )
    if opportunity is None:
        raise AppError("opportunity_not_found", "Opportunity was not found", 404)
    customer = visible_customer(db, user, opportunity.customer_id, True)
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("stage_id") and changes["stage_id"] != opportunity.stage_id:
        stage = tenant_stage(db, opportunity.company_id, str(changes["stage_id"]))
        db.add(
            OpportunityStageHistory(
                opportunity_id=opportunity.id,
                from_stage_id=opportunity.stage_id,
                to_stage_id=stage.id,
                actor_user_id=user.id,
            )
        )
        add_event(
            db,
            customer,
            "opportunity_stage_changed",
            "商机阶段变更",
            user.id,
            {
                "opportunity_id": opportunity.id,
                "from_stage_id": opportunity.stage_id,
                "to_stage_id": stage.id,
            },
        )
    for field, value in changes.items():
        setattr(opportunity, field, value)
    db.commit()
    db.refresh(opportunity)
    return opportunity


@router.get(
    "/tenant/opportunities/{opportunity_id}/history", response_model=list[StageHistoryResponse]
)
def opportunity_history(
    opportunity_id: str,
    user: Annotated[User, Depends(require_permission(Permission.CUSTOMER_READ))],
    db: Annotated[Session, Depends(get_db)],
) -> list[OpportunityStageHistory]:
    opportunity = db.scalar(
        select(Opportunity).where(
            Opportunity.id == opportunity_id, Opportunity.company_id == user.company_id
        )
    )
    if opportunity is None:
        raise AppError("opportunity_not_found", "Opportunity was not found", 404)
    visible_customer(db, user, opportunity.customer_id)
    return list(
        db.scalars(
            select(OpportunityStageHistory)
            .where(OpportunityStageHistory.opportunity_id == opportunity.id)
            .order_by(OpportunityStageHistory.changed_at)
        )
    )


@router.get("/tenant/opportunities/funnel/summary", response_model=FunnelResponse)
def funnel_summary(
    user: Annotated[User, Depends(require_permission(Permission.CUSTOMER_READ))],
    db: Annotated[Session, Depends(get_db)],
) -> FunnelResponse:
    conditions = [Opportunity.company_id == user.company_id]
    if not can_manage_all(db, user):
        employee = current_employee(db, user)
        conditions.append(Opportunity.owner_employee_id == (employee.id if employee else ""))
    rows = db.execute(
        select(
            Opportunity.stage_id,
            func.count(Opportunity.id),
            func.coalesce(func.sum(Opportunity.expected_amount), 0),
        )
        .where(*conditions)
        .group_by(Opportunity.stage_id)
    ).all()
    aggregates = {row[0]: (row[1], Decimal(row[2])) for row in rows}
    stages = db.scalars(
        select(OpportunityStage)
        .where(OpportunityStage.company_id == user.company_id, OpportunityStage.is_active.is_(True))
        .order_by(OpportunityStage.sort_order)
    )
    return FunnelResponse(
        items=[
            FunnelItem(
                stage_id=stage.id,
                stage_name=stage.name,
                count=aggregates.get(stage.id, (0, Decimal("0")))[0],
                expected_amount=aggregates.get(stage.id, (0, Decimal("0")))[1],
            )
            for stage in stages
        ]
    )
