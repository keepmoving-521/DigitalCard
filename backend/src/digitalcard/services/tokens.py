import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import jwt
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from digitalcard.core.config import Settings
from digitalcard.core.errors import AppError
from digitalcard.core.time import utc_now
from digitalcard.models.account import RefreshSession, User


def create_access_token(
    user: User,
    settings: Settings,
    session_id: str,
    expires_delta: timedelta | None = None,
) -> str:
    now = datetime.now(UTC)
    expires_at = now + (expires_delta or timedelta(minutes=settings.access_token_minutes))
    return jwt.encode(
        {
            "sub": user.id,
            "role": user.role,
            "ver": user.token_version,
            "sid": session_id,
            "type": "access",
            "iat": now,
            "exp": expires_at,
            "jti": str(uuid4()),
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
        },
        settings.secret_key.get_secret_value(),
        algorithm="HS256",
    )


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=["HS256"],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={
                "require": [
                    "sub",
                    "ver",
                    "sid",
                    "type",
                    "iat",
                    "exp",
                    "jti",
                    "iss",
                    "aud",
                ]
            },
        )
    except jwt.ExpiredSignatureError as exc:
        raise AppError("token_expired", "Access token has expired", 401) from exc
    except jwt.InvalidTokenError as exc:
        raise AppError("invalid_token", "Access token is invalid", 401) from exc
    if payload.get("type") != "access":
        raise AppError("invalid_token", "Access token is invalid", 401)
    return payload


def hash_refresh_token(token: str, settings: Settings) -> str:
    return hmac.new(
        settings.secret_key.get_secret_value().encode(), token.encode(), hashlib.sha256
    ).hexdigest()


def create_refresh_session(
    db: Session,
    user: User,
    settings: Settings,
    ip_address: str | None,
    user_agent: str | None,
) -> tuple[str, RefreshSession]:
    raw_token = secrets.token_urlsafe(48)
    session = RefreshSession(
        id=str(uuid4()),
        user_id=user.id,
        token_hash=hash_refresh_token(raw_token, settings),
        expires_at=utc_now() + timedelta(days=settings.refresh_token_days),
        ip_address=ip_address,
        user_agent=user_agent[:512] if user_agent else None,
    )
    db.add(session)
    return raw_token, session


def revoke_all_sessions(db: Session, user_id: str) -> None:
    db.execute(
        update(RefreshSession)
        .where(RefreshSession.user_id == user_id, RefreshSession.revoked_at.is_(None))
        .values(revoked_at=utc_now())
    )


def rotate_refresh_session(
    db: Session,
    raw_token: str,
    settings: Settings,
    ip_address: str | None,
    user_agent: str | None,
) -> tuple[User, str, RefreshSession]:
    session = db.scalar(
        select(RefreshSession).where(
            RefreshSession.token_hash == hash_refresh_token(raw_token, settings)
        )
    )
    if session is None:
        raise AppError("invalid_refresh_token", "Refresh session is invalid", 401)

    user = db.get(User, session.user_id)
    if user is None:
        raise AppError("invalid_refresh_token", "Refresh session is invalid", 401)
    if session.revoked_at is not None:
        if session.replaced_by_id is not None:
            revoke_all_sessions(db, user.id)
            user.token_version += 1
            db.commit()
        raise AppError("refresh_token_reused", "Refresh session has already been used", 401)
    if session.expires_at <= utc_now():
        session.revoked_at = utc_now()
        db.commit()
        raise AppError("refresh_token_expired", "Refresh session has expired", 401)
    if not user.is_active:
        session.revoked_at = utc_now()
        db.commit()
        raise AppError("account_disabled", "Account is disabled", 403)

    new_raw_token, new_session = create_refresh_session(db, user, settings, ip_address, user_agent)
    session.revoked_at = utc_now()
    session.last_used_at = utc_now()
    session.replaced_by_id = new_session.id
    db.commit()
    db.refresh(user)
    return user, new_raw_token, new_session


def revoke_refresh_session(db: Session, raw_token: str, settings: Settings) -> None:
    session = db.scalar(
        select(RefreshSession).where(
            RefreshSession.token_hash == hash_refresh_token(raw_token, settings)
        )
    )
    if session is not None and session.revoked_at is None:
        session.revoked_at = utc_now()
        db.commit()
