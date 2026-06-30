from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from digitalcard.api.dependencies import AdminUser
from digitalcard.core.errors import AppError
from digitalcard.db.session import get_db
from digitalcard.models.account import LoginAudit, User, UserRole
from digitalcard.models.organization import Company, CompanyStatus, Department, TenantRole
from digitalcard.schemas.account import (
    LoginAuditResponse,
    PasswordResetRequest,
    UserCreateRequest,
    UserResponse,
    UserStatusRequest,
)
from digitalcard.services.passwords import hash_password, validate_password
from digitalcard.services.tokens import revoke_all_sessions

router = APIRouter(prefix="/admin", tags=["administration"])


@router.get("/users", response_model=list[UserResponse], summary="List users")
def list_users(
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[User]:
    return list(
        db.scalars(select(User).order_by(User.created_at.desc()).offset(offset).limit(limit))
    )


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create user",
)
def create_user(
    payload: UserCreateRequest,
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if db.scalar(select(func.count()).select_from(User).where(User.email == payload.email)):
        raise AppError("email_exists", "An account with this email already exists", 409)
    if payload.role == UserRole.PLATFORM_ADMIN:
        if payload.company_id is not None or payload.department_id is not None:
            raise AppError(
                "invalid_platform_account", "Platform accounts cannot belong to a company", 422
            )
    else:
        if payload.company_id is None:
            raise AppError("company_required", "Company is required for tenant accounts", 422)
        company = db.get(Company, payload.company_id)
        if company is None:
            raise AppError("company_not_found", "Company was not found", 404)
        if company.status != CompanyStatus.ACTIVE.value:
            raise AppError("company_suspended", "Company workspace is suspended", 409)
        if not db.scalar(
            select(TenantRole.id).where(
                TenantRole.company_id == company.id,
                TenantRole.code == payload.role.value,
            )
        ):
            raise AppError("invalid_tenant_role", "Role is not available in this company", 422)
        if payload.department_id:
            department = db.scalar(
                select(Department).where(
                    Department.id == payload.department_id,
                    Department.company_id == company.id,
                )
            )
            if department is None:
                raise AppError("department_not_found", "Department was not found", 404)
    validate_password(payload.password, payload.email)
    user = User(
        email=payload.email,
        display_name=payload.display_name,
        password_hash=hash_password(payload.password),
        role=payload.role.value,
        company_id=payload.company_id,
        department_id=payload.department_id,
        must_change_password=payload.must_change_password,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}/status", response_model=UserResponse, summary="Set user status")
def set_user_status(
    user_id: str,
    payload: UserStatusRequest,
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise AppError("user_not_found", "User was not found", 404)
    if user.id == admin.id and not payload.is_active:
        raise AppError("cannot_disable_self", "Administrators cannot disable themselves", 409)
    if user.is_active != payload.is_active:
        user.is_active = payload.is_active
        user.token_version += 1
        user.failed_login_attempts = 0
        user.locked_until = None
        revoke_all_sessions(db, user.id)
        db.commit()
        db.refresh(user)
    return user


@router.post(
    "/users/{user_id}/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Reset user password",
)
def reset_password(
    user_id: str,
    payload: PasswordResetRequest,
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
) -> None:
    user = db.get(User, user_id)
    if user is None:
        raise AppError("user_not_found", "User was not found", 404)
    validate_password(payload.new_password, user.email)
    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = payload.must_change_password
    user.token_version += 1
    user.failed_login_attempts = 0
    user.locked_until = None
    revoke_all_sessions(db, user.id)
    db.commit()


@router.get("/login-audits", response_model=list[LoginAuditResponse], summary="List login audits")
def list_login_audits(
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[LoginAudit]:
    return list(
        db.scalars(
            select(LoginAudit).order_by(LoginAudit.created_at.desc()).offset(offset).limit(limit)
        )
    )
