from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from digitalcard.api.dependencies import require_permission
from digitalcard.db.session import get_db
from digitalcard.models.account import User
from digitalcard.models.card import CardStatus, DigitalCard
from digitalcard.models.employee import Employee
from digitalcard.models.lead import Lead
from digitalcard.models.organization import Company, Department
from digitalcard.schemas.operations import (
    MonitoringResponse,
    OnboardingResponse,
    OnboardingStep,
    RateMetric,
)
from digitalcard.services.metrics import runtime_metrics
from digitalcard.services.permissions import Permission

router = APIRouter(tags=["operations"])


@router.get("/tenant/onboarding", response_model=OnboardingResponse)
def onboarding_status(
    user: Annotated[User, Depends(require_permission(Permission.COMPANY_READ))],
    db: Annotated[Session, Depends(get_db)],
) -> OnboardingResponse:
    company = db.get(Company, user.company_id)
    department_count = (
        db.scalar(
            select(func.count())
            .select_from(Department)
            .where(Department.company_id == user.company_id)
        )
        or 0
    )
    employee_count = (
        db.scalar(
            select(func.count()).select_from(Employee).where(Employee.company_id == user.company_id)
        )
        or 0
    )
    published_cards = (
        db.scalar(
            select(func.count())
            .select_from(DigitalCard)
            .where(
                DigitalCard.company_id == user.company_id,
                DigitalCard.status == CardStatus.PUBLISHED.value,
            )
        )
        or 0
    )
    steps = [
        OnboardingStep(
            code="company",
            name="完善企业资料",
            completed=bool(company and company.name and company.contact_email),
            path="/company/settings",
        ),
        OnboardingStep(
            code="department",
            name="建立部门",
            completed=department_count > 0,
            path="/company/departments",
        ),
        OnboardingStep(
            code="employee",
            name="录入或邀请员工",
            completed=employee_count > 0,
            path="/company/employees",
        ),
        OnboardingStep(
            code="card",
            name="发布并分享第一张名片",
            completed=published_cards > 0,
            path="/my-card",
        ),
    ]
    completed_count = sum(step.completed for step in steps)
    return OnboardingResponse(
        completed=completed_count == len(steps),
        completed_count=completed_count,
        total_count=len(steps),
        steps=steps,
    )


def rate_metric(value: object) -> RateMetric:
    if not isinstance(value, dict):
        return RateMetric(attempts=0, successes=0, success_rate=None)
    return RateMetric.model_validate(value)


@router.get("/tenant/monitoring", response_model=MonitoringResponse)
def monitoring(
    user: Annotated[User, Depends(require_permission(Permission.AUDIT_READ))],
    db: Annotated[Session, Depends(get_db)],
) -> MonitoringResponse:
    snapshot = runtime_metrics.snapshot()
    business = snapshot["business"]
    assert isinstance(business, dict)
    claimed = list(
        db.execute(
            select(Lead.created_at, Lead.claimed_at).where(
                Lead.company_id == user.company_id,
                Lead.claimed_at.is_not(None),
            )
        )
    )
    average_minutes = (
        round(
            sum((claimed_at - created_at).total_seconds() for created_at, claimed_at in claimed)
            / len(claimed)
            / 60,
            2,
        )
        if claimed
        else None
    )
    return MonitoringResponse(
        requests=int(snapshot["requests"]),
        errors=int(snapshot["errors"]),
        error_rate=float(snapshot["error_rate"]),
        p95_duration_ms=float(snapshot["p95_duration_ms"]),
        card_publish=rate_metric(business.get("card_publish")),
        public_card=rate_metric(business.get("public_card")),
        lead_submit=rate_metric(business.get("lead_submit")),
        average_first_response_minutes=average_minutes,
    )
