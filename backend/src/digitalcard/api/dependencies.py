from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from digitalcard.core.config import Settings, get_settings
from digitalcard.core.errors import AppError
from digitalcard.db.session import get_db
from digitalcard.models.account import RefreshSession, User, UserRole
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


def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != UserRole.ADMIN.value:
        raise AppError("permission_denied", "Administrator permission is required", 403)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require_admin)]
