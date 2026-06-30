from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from digitalcard.core.config import Settings, get_settings
from digitalcard.core.errors import AppError
from digitalcard.db.session import get_db
from digitalcard.models.account import RefreshSession, User, UserRole
from digitalcard.models.organization import Company, CompanyStatus
from digitalcard.services.permissions import Permission, permissions_for_user
from digitalcard.services.tokens import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppError("auth_required", "Authentication is required", 401)
    payload = decode_access_token(credentials.credentials, settings)
    user = db.get(User, payload["sub"])
    if user is None:
        raise AppError("invalid_token", "Access token is invalid", 401)
    if not user.is_active:
        raise AppError("account_disabled", "Account is disabled", 403)
    if user.company_id is not None:
        company = db.get(Company, user.company_id)
        if company is None or company.status != CompanyStatus.ACTIVE.value:
            raise AppError("company_suspended", "Company workspace is suspended", 403)
    if payload["ver"] != user.token_version:
        raise AppError("token_revoked", "Access token has been revoked", 401)
    refresh_session = db.get(RefreshSession, payload["sid"])
    if (
        refresh_session is None
        or refresh_session.user_id != user.id
        or refresh_session.revoked_at is not None
    ):
        raise AppError("session_revoked", "Session has been revoked", 401)
    return user


def require_platform_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != UserRole.PLATFORM_ADMIN.value:
        raise AppError("permission_denied", "Platform administrator permission is required", 403)
    return user


def require_tenant_user(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.company_id is None or user.role == UserRole.PLATFORM_ADMIN.value:
        raise AppError("tenant_required", "A company workspace is required", 403)
    return user


def require_permission(permission: Permission):
    def dependency(
        user: Annotated[User, Depends(require_tenant_user)],
        db: Annotated[Session, Depends(get_db)],
    ) -> User:
        if permission.value not in permissions_for_user(db, user):
            raise AppError("permission_denied", "Permission is required", 403)
        return user

    return dependency


CurrentUser = Annotated[User, Depends(get_current_user)]
TenantUser = Annotated[User, Depends(require_tenant_user)]
PlatformAdmin = Annotated[User, Depends(require_platform_admin)]
AdminUser = PlatformAdmin
