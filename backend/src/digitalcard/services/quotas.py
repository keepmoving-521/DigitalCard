from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from digitalcard.core.errors import AppError
from digitalcard.core.time import utc_now
from digitalcard.models.card import DigitalCard
from digitalcard.models.employee import Employee
from digitalcard.models.product import Material
from digitalcard.models.saas import SaasPlan, SubscriptionStatus, TenantSubscription


@dataclass
class QuotaUsage:
    employees: int
    cards: int
    storage_bytes: int


def subscription_and_plan(db: Session, company_id: str) -> tuple[TenantSubscription, SaasPlan]:
    subscription = db.get(TenantSubscription, company_id)
    if subscription is None:
        raise AppError("subscription_missing", "Tenant subscription is not configured", 409)
    plan = db.get(SaasPlan, subscription.plan_id)
    if plan is None or not plan.is_active:
        raise AppError("plan_unavailable", "Tenant plan is unavailable", 409)
    if subscription.expires_at <= utc_now() and subscription.status not in {
        SubscriptionStatus.CANCELLED.value,
        SubscriptionStatus.CANCEL_PENDING.value,
    }:
        subscription.status = SubscriptionStatus.EXPIRED.value
        db.flush()
    return subscription, plan


def usage(db: Session, company_id: str) -> QuotaUsage:
    return QuotaUsage(
        employees=db.scalar(
            select(func.count()).select_from(Employee).where(Employee.company_id == company_id)
        )
        or 0,
        cards=db.scalar(
            select(func.count())
            .select_from(DigitalCard)
            .where(DigitalCard.company_id == company_id)
        )
        or 0,
        storage_bytes=db.scalar(
            select(func.coalesce(func.sum(Material.size_bytes), 0)).where(
                Material.company_id == company_id
            )
        )
        or 0,
    )


def enforce_quota(db: Session, company_id: str, resource: str, increment: int = 1) -> None:
    subscription, plan = subscription_and_plan(db, company_id)
    if subscription.status in {
        SubscriptionStatus.EXPIRED.value,
        SubscriptionStatus.CANCEL_PENDING.value,
        SubscriptionStatus.CANCELLED.value,
    }:
        raise AppError("subscription_restricted", "Subscription does not allow new resources", 409)
    current = usage(db, company_id)
    used, limit = {
        "employees": (current.employees, plan.employee_limit),
        "cards": (current.cards, plan.card_limit),
        "storage": (current.storage_bytes, plan.storage_limit_bytes),
    }[resource]
    if used + increment > limit:
        raise AppError(
            "quota_exceeded",
            "Plan quota is exceeded; existing data remains available",
            409,
            {"resource": resource, "used": used, "limit": limit, "requested": increment},
        )
