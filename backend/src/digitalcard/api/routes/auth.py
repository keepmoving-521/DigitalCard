from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from digitalcard.api.dependencies import CurrentUser
from digitalcard.core.config import Settings, get_settings
from digitalcard.core.errors import AppError
from digitalcard.core.time import utc_now
from digitalcard.db.session import get_db
from digitalcard.models.account import LoginAudit, RefreshSession, User
from digitalcard.models.organization import Company, CompanyStatus
from digitalcard.schemas.account import (
    CurrentUserResponse,
    LoginRequest,
    PasswordChangeRequest,
    SessionResponse,
    UserResponse,
)
from digitalcard.services.passwords import (
    dummy_password_hash,
    hash_password,
    validate_password,
    verify_password,
)
from digitalcard.services.permissions import permissions_for_user
from digitalcard.services.tokens import (
    create_access_token,
    create_refresh_session,
    revoke_all_sessions,
    revoke_refresh_session,
    rotate_refresh_session,
)

router = APIRouter(prefix="/auth")


def client_metadata(request: Request) -> tuple[str | None, str | None]:
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return ip_address, user_agent[:512] if user_agent else None


def add_login_audit(
    db: Session,
    request: Request,
    email: str,
    success: bool,
    reason: str,
    user_id: str | None = None,
) -> None:
    ip_address, user_agent = client_metadata(request)
    db.add(
        LoginAudit(
            user_id=user_id,
            email=email,
            success=success,
            reason=reason,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    )


def set_refresh_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=token,
        max_age=int(timedelta(days=settings.refresh_token_days).total_seconds()),
        httponly=True,
        secure=settings.app_env == "production",
        samesite="lax",
        path="/api/v1/auth",
    )


def clear_refresh_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        httponly=True,
        secure=settings.app_env == "production",
        samesite="lax",
        path="/api/v1/auth",
    )


def session_response(
    db: Session, user: User, refresh_session: RefreshSession, settings: Settings
) -> SessionResponse:
    current_user = CurrentUserResponse(
        **UserResponse.model_validate(user).model_dump(),
        permissions=sorted(permissions_for_user(db, user)),
    )
    return SessionResponse(
        access_token=create_access_token(user, settings, refresh_session.id),
        expires_in=settings.access_token_minutes * 60,
        user=current_user,
    )


@router.post("/login", response_model=SessionResponse, summary="Sign in")
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SessionResponse:
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None:
        verify_password(payload.password, dummy_password_hash())
        add_login_audit(db, request, payload.email, False, "invalid_credentials")
        db.commit()
        raise AppError("invalid_credentials", "Email or password is incorrect", 401)
    if not user.is_active:
        add_login_audit(db, request, payload.email, False, "account_disabled", user.id)
        db.commit()
        raise AppError("account_disabled", "Account is disabled", 403)

    now = utc_now()
    if user.locked_until is not None and user.locked_until > now:
        add_login_audit(db, request, payload.email, False, "account_locked", user.id)
        db.commit()
        retry_after = max(1, int((user.locked_until - now).total_seconds()))
        raise AppError(
            "account_locked",
            "Too many failed attempts; try again later",
            429,
            {"retry_after": retry_after},
        )
    if user.locked_until is not None:
        user.locked_until = None
        user.failed_login_attempts = 0

    valid, updated_hash = verify_password(payload.password, user.password_hash)
    if not valid:
        user.failed_login_attempts += 1
        locked = user.failed_login_attempts >= settings.login_max_attempts
        if locked:
            user.locked_until = now + timedelta(minutes=settings.login_lock_minutes)
        add_login_audit(
            db,
            request,
            payload.email,
            False,
            "account_locked" if locked else "invalid_credentials",
            user.id,
        )
        db.commit()
        if locked:
            raise AppError(
                "account_locked",
                "Too many failed attempts; try again later",
                429,
                {"retry_after": settings.login_lock_minutes * 60},
            )
        raise AppError("invalid_credentials", "Email or password is incorrect", 401)

    if updated_hash:
        user.password_hash = updated_hash
    if user.company_id is not None:
        company = db.get(Company, user.company_id)
        if company is None or company.status != CompanyStatus.ACTIVE.value:
            add_login_audit(db, request, payload.email, False, "company_suspended", user.id)
            db.commit()
            raise AppError("company_suspended", "Company workspace is suspended", 403)
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    ip_address, user_agent = client_metadata(request)
    refresh_token, refresh_session = create_refresh_session(
        db, user, settings, ip_address, user_agent
    )
    add_login_audit(db, request, payload.email, True, "success", user.id)
    db.commit()
    db.refresh(user)
    set_refresh_cookie(response, refresh_token, settings)
    return session_response(db, user, refresh_session, settings)


@router.post("/refresh", response_model=SessionResponse, summary="Refresh session")
def refresh(
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SessionResponse:
    refresh_token = request.cookies.get(settings.refresh_cookie_name)
    if not refresh_token:
        raise AppError("refresh_required", "Refresh session is required", 401)
    ip_address, user_agent = client_metadata(request)
    user, new_refresh_token, refresh_session = rotate_refresh_session(
        db, refresh_token, settings, ip_address, user_agent
    )
    set_refresh_cookie(response, new_refresh_token, settings)
    return session_response(db, user, refresh_session, settings)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Sign out")
def logout(
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    refresh_token = request.cookies.get(settings.refresh_cookie_name)
    if refresh_token:
        revoke_refresh_session(db, refresh_token, settings)
    clear_refresh_cookie(response, settings)


@router.get("/me", response_model=CurrentUserResponse, summary="Get current user")
def me(user: CurrentUser, db: Annotated[Session, Depends(get_db)]) -> CurrentUserResponse:
    return CurrentUserResponse(
        **UserResponse.model_validate(user).model_dump(),
        permissions=sorted(permissions_for_user(db, user)),
    )


@router.put("/me/password", status_code=status.HTTP_204_NO_CONTENT, summary="Change password")
def change_password(
    payload: PasswordChangeRequest,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> None:
    valid, _ = verify_password(payload.current_password, user.password_hash)
    if not valid:
        raise AppError("invalid_current_password", "Current password is incorrect", 400)
    validate_password(payload.new_password, user.email)
    same_password, _ = verify_password(payload.new_password, user.password_hash)
    if same_password:
        raise AppError("password_unchanged", "New password must be different", 422)
    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    user.token_version += 1
    revoke_all_sessions(db, user.id)
    db.commit()
