from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from digitalcard.api.dependencies import PlatformAdmin
from digitalcard.core.errors import AppError
from digitalcard.db.session import get_db
from digitalcard.models.account import User
from digitalcard.models.organization import Company, CompanyStatus
from digitalcard.schemas.organization import (
    CompanyCreateRequest,
    CompanyResponse,
    CompanyStatusRequest,
)
from digitalcard.services.crm import seed_opportunity_stages
from digitalcard.services.permissions import seed_tenant_roles
from digitalcard.services.tenancy import record_tenant_audit
from digitalcard.services.tokens import revoke_all_sessions

router = APIRouter(prefix="/platform/companies", tags=["platform"])


@router.get("", response_model=list[CompanyResponse], summary="List companies")
def list_companies(
    _: PlatformAdmin,
    db: Annotated[Session, Depends(get_db)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[Company]:
    return list(
        db.scalars(select(Company).order_by(Company.created_at.desc()).offset(offset).limit(limit))
    )


@router.post(
    "",
    response_model=CompanyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create company",
)
def create_company(
    payload: CompanyCreateRequest,
    admin: PlatformAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> Company:
    if db.scalar(select(Company.id).where(Company.code == payload.code)):
        raise AppError("company_code_exists", "Company code already exists", 409)
    company = Company(**payload.model_dump(), status=CompanyStatus.ACTIVE.value)
    db.add(company)
    db.flush()
    seed_tenant_roles(db, company.id)
    seed_opportunity_stages(db, company.id)
    record_tenant_audit(
        db,
        company.id,
        admin.id,
        "company.created",
        "company",
        company.id,
        {"code": company.code, "name": company.name},
    )
    db.commit()
    db.refresh(company)
    return company


@router.patch("/{company_id}/status", response_model=CompanyResponse, summary="Set company status")
def set_company_status(
    company_id: str,
    payload: CompanyStatusRequest,
    admin: PlatformAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> Company:
    company = db.get(Company, company_id)
    if company is None:
        raise AppError("company_not_found", "Company was not found", 404)
    if company.status != payload.status.value:
        previous = company.status
        company.status = payload.status.value
        if payload.status == CompanyStatus.SUSPENDED:
            users = list(db.scalars(select(User).where(User.company_id == company.id)))
            for user in users:
                user.token_version += 1
                revoke_all_sessions(db, user.id)
        record_tenant_audit(
            db,
            company.id,
            admin.id,
            "company.status_changed",
            "company",
            company.id,
            {"before": previous, "after": company.status},
        )
        db.commit()
        db.refresh(company)
    return company
