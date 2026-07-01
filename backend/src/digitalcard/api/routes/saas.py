import hashlib
import secrets
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from digitalcard.api.dependencies import PlatformAdmin
from digitalcard.core.errors import AppError
from digitalcard.core.time import utc_now
from digitalcard.db.session import get_db
from digitalcard.models.account import User, UserRole
from digitalcard.models.organization import Company, CompanyStatus
from digitalcard.models.saas import (
    PlatformOperationLog,
    SaasPlan,
    SubscriptionRenewal,
    SubscriptionStatus,
    TenantSubscription,
    TenantSupportGrant,
)
from digitalcard.schemas.saas import (
    CancelRequest,
    PlanPayload,
    PlanResponse,
    SubscriptionResponse,
    SubscriptionUpdate,
    SupportGrantRequest,
    TenantOverview,
)
from digitalcard.services.quotas import subscription_and_plan, usage

router = APIRouter(prefix="/platform/saas", tags=["platform SaaS operations"])


def platform_log(
    db: Session,
    actor_id: str,
    action: str,
    company_id: str | None = None,
    details: str | None = None,
) -> None:
    db.add(
        PlatformOperationLog(
            company_id=company_id, actor_user_id=actor_id, action=action, details=details
        )
    )


def normalize_datetime(value):  # type: ignore[no-untyped-def]
    return value.replace(tzinfo=None) if value.tzinfo else value


def subscription_response(db: Session, company_id: str) -> SubscriptionResponse:
    subscription, plan = subscription_and_plan(db, company_id)
    current = usage(db, company_id)
    values = {
        "employees": current.employees,
        "cards": current.cards,
        "storage_bytes": current.storage_bytes,
    }
    limits = {
        "employees": plan.employee_limit,
        "cards": plan.card_limit,
        "storage_bytes": plan.storage_limit_bytes,
    }
    warnings = [name for name in values if values[name] >= limits[name] * 0.8]
    if subscription.expires_at <= utc_now() + timedelta(days=7):
        warnings.append("expires_soon")
    return SubscriptionResponse(
        company_id=company_id,
        plan_id=plan.id,
        plan_name=plan.name,
        status=subscription.status,
        starts_at=subscription.starts_at,
        expires_at=subscription.expires_at,
        cancel_requested_at=subscription.cancel_requested_at,
        cancel_effective_at=subscription.cancel_effective_at,
        data_cleanup_after=subscription.data_cleanup_after,
        usage=values,
        limits=limits,
        warnings=warnings,
    )


@router.get("/plans", response_model=list[PlanResponse])
def list_plans(_: PlatformAdmin, db: Annotated[Session, Depends(get_db)]):
    return list(db.scalars(select(SaasPlan).order_by(SaasPlan.created_at)))


@router.post("/plans", response_model=PlanResponse, status_code=201)
def create_plan(
    payload: PlanPayload, admin: PlatformAdmin, db: Annotated[Session, Depends(get_db)]
):
    if db.scalar(select(SaasPlan.id).where(SaasPlan.code == payload.code)):
        raise AppError("plan_code_exists", "Plan code already exists", 409)
    plan = SaasPlan(**payload.model_dump())
    db.add(plan)
    db.flush()
    platform_log(db, admin.id, "plan.created", details=plan.code)
    db.commit()
    db.refresh(plan)
    return plan


@router.put("/plans/{plan_id}", response_model=PlanResponse)
def update_plan(
    plan_id: str,
    payload: PlanPayload,
    admin: PlatformAdmin,
    db: Annotated[Session, Depends(get_db)],
):
    plan = db.get(SaasPlan, plan_id)
    if plan is None:
        raise AppError("plan_not_found", "Plan was not found", 404)
    for key, value in payload.model_dump().items():
        setattr(plan, key, value)
    platform_log(db, admin.id, "plan.updated", details=plan.code)
    db.commit()
    db.refresh(plan)
    return plan


@router.get("/tenants", response_model=list[TenantOverview])
def tenant_overviews(_: PlatformAdmin, db: Annotated[Session, Depends(get_db)]):
    result = []
    for company in db.scalars(select(Company).order_by(Company.created_at.desc())):
        subscription = subscription_response(db, company.id)
        alerts = list(subscription.warnings)
        if company.status != CompanyStatus.ACTIVE.value:
            alerts.append("workspace_suspended")
        if subscription.status in {SubscriptionStatus.EXPIRED, SubscriptionStatus.CANCEL_PENDING}:
            alerts.append(subscription.status.value)
        result.append(
            TenantOverview(
                company_id=company.id,
                company_name=company.name,
                company_status=company.status,
                subscription=subscription,
                alerts=alerts,
            )
        )
    return result


@router.put("/tenants/{company_id}/subscription", response_model=SubscriptionResponse)
def change_subscription(
    company_id: str,
    payload: SubscriptionUpdate,
    admin: PlatformAdmin,
    db: Annotated[Session, Depends(get_db)],
):
    company = db.get(Company, company_id)
    plan = db.get(SaasPlan, payload.plan_id)
    if company is None:
        raise AppError("company_not_found", "Company was not found", 404)
    if plan is None or not plan.is_active:
        raise AppError("plan_not_found", "Active plan was not found", 404)
    expires_at = normalize_datetime(payload.expires_at)
    subscription = db.get(TenantSubscription, company_id)
    if subscription is None:
        subscription = TenantSubscription(
            company_id=company_id,
            plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE.value,
            starts_at=utc_now(),
            expires_at=expires_at,
        )
        db.add(subscription)
        previous = utc_now()
    else:
        previous = subscription.expires_at
        subscription.plan_id = plan.id
        subscription.expires_at = expires_at
        subscription.status = SubscriptionStatus.ACTIVE.value
        subscription.cancel_requested_at = None
        subscription.cancel_effective_at = None
    db.add(
        SubscriptionRenewal(
            company_id=company_id,
            plan_id=plan.id,
            previous_expires_at=previous,
            new_expires_at=expires_at,
            note=payload.note,
            actor_user_id=admin.id,
        )
    )
    platform_log(
        db,
        admin.id,
        "subscription.changed",
        company_id,
        f"plan={plan.code};expires={expires_at.isoformat()}",
    )
    db.commit()
    return subscription_response(db, company_id)


@router.post("/tenants/{company_id}/cancel", response_model=SubscriptionResponse)
def request_cancellation(
    company_id: str,
    payload: CancelRequest,
    admin: PlatformAdmin,
    db: Annotated[Session, Depends(get_db)],
):
    company = db.get(Company, company_id)
    if company is None:
        raise AppError("company_not_found", "Company was not found", 404)
    if payload.confirmation != company.code:
        raise AppError(
            "cancellation_confirmation_invalid",
            "Enter the tenant code to confirm cancellation",
            422,
        )
    subscription, _ = subscription_and_plan(db, company_id)
    now = utc_now()
    subscription.status = SubscriptionStatus.CANCEL_PENDING.value
    subscription.cancel_requested_at = now
    subscription.cancel_effective_at = now + timedelta(days=payload.cooling_days)
    subscription.data_cleanup_after = subscription.cancel_effective_at + timedelta(days=30)
    platform_log(
        db,
        admin.id,
        "tenant.cancellation_requested",
        company_id,
        f"effective={subscription.cancel_effective_at.isoformat()};export_available=true",
    )
    db.commit()
    return subscription_response(db, company_id)


@router.post("/tenants/{company_id}/cancel/confirm", response_model=SubscriptionResponse)
def confirm_cancellation(
    company_id: str, admin: PlatformAdmin, db: Annotated[Session, Depends(get_db)]
):
    company = db.get(Company, company_id)
    subscription = db.get(TenantSubscription, company_id)
    if company is None or subscription is None:
        raise AppError("company_not_found", "Company was not found", 404)
    if (
        subscription.status != SubscriptionStatus.CANCEL_PENDING.value
        or not subscription.cancel_effective_at
    ):
        raise AppError("cancellation_not_pending", "Cancellation is not pending", 409)
    if utc_now() < subscription.cancel_effective_at:
        raise AppError(
            "cancellation_cooling_period", "Cancellation cooling period has not ended", 409
        )
    subscription.status = SubscriptionStatus.CANCELLED.value
    subscription.cancelled_at = utc_now()
    company.status = CompanyStatus.SUSPENDED.value
    platform_log(db, admin.id, "tenant.cancelled", company_id, "data_preserved_until_cleanup_date")
    db.commit()
    return subscription_response(db, company_id)


@router.get("/logs")
def operation_logs(_: PlatformAdmin, db: Annotated[Session, Depends(get_db)]):
    return list(
        db.scalars(
            select(PlatformOperationLog).order_by(PlatformOperationLog.created_at.desc()).limit(500)
        )
    )


@router.post("/support-grants", response_model=dict, status_code=201)
def create_support_grant(
    payload: SupportGrantRequest, admin: PlatformAdmin, db: Annotated[Session, Depends(get_db)]
):
    company = db.get(Company, payload.company_id)
    target = db.get(User, payload.granted_to_user_id)
    if company is None:
        raise AppError("company_not_found", "Company was not found", 404)
    if target is None or target.role != UserRole.PLATFORM_ADMIN.value:
        raise AppError(
            "support_user_invalid", "Support recipient must be a platform administrator", 422
        )
    expiry = normalize_datetime(payload.expires_at)
    token = secrets.token_urlsafe(32)
    grant = TenantSupportGrant(
        company_id=company.id,
        granted_to_user_id=target.id,
        granted_by_user_id=admin.id,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        reason=payload.reason,
        expires_at=expiry,
    )
    db.add(grant)
    db.flush()
    platform_log(
        db,
        admin.id,
        "support.granted",
        company.id,
        f"grant={grant.id};to={target.id};expires={expiry.isoformat()};reason={payload.reason}",
    )
    db.commit()
    return {"id": grant.id, "token": token, "expires_at": expiry}


@router.post("/support-grants/{grant_id}/revoke")
def revoke_support_grant(
    grant_id: str, admin: PlatformAdmin, db: Annotated[Session, Depends(get_db)]
):
    grant = db.get(TenantSupportGrant, grant_id)
    if grant is None:
        raise AppError("support_grant_not_found", "Support grant was not found", 404)
    grant.revoked_at = utc_now()
    platform_log(db, admin.id, "support.revoked", grant.company_id, f"grant={grant.id}")
    db.commit()
    return {"revoked": True}


@router.get("/support/tenants/{company_id}/overview", response_model=TenantOverview)
def support_tenant_overview(
    company_id: str,
    admin: PlatformAdmin,
    db: Annotated[Session, Depends(get_db)],
    token: Annotated[str, Header(alias="X-Support-Grant-Token")],
):
    grant = db.scalar(
        select(TenantSupportGrant).where(
            TenantSupportGrant.company_id == company_id,
            TenantSupportGrant.granted_to_user_id == admin.id,
            TenantSupportGrant.token_hash == hashlib.sha256(token.encode()).hexdigest(),
            TenantSupportGrant.revoked_at.is_(None),
            TenantSupportGrant.expires_at > utc_now(),
        )
    )
    if grant is None:
        raise AppError(
            "support_authorization_required", "Valid tenant support authorization is required", 403
        )
    company = db.get(Company, company_id)
    if company is None:
        raise AppError("company_not_found", "Company was not found", 404)
    platform_log(
        db,
        admin.id,
        "support.tenant_overview_accessed",
        company.id,
        f"grant={grant.id};reason={grant.reason}",
    )
    db.commit()
    subscription = subscription_response(db, company.id)
    return TenantOverview(
        company_id=company.id,
        company_name=company.name,
        company_status=company.status,
        subscription=subscription,
        alerts=subscription.warnings,
    )
