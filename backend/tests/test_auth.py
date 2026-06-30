from collections.abc import AsyncIterator
from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from digitalcard.core.config import get_settings
from digitalcard.db.session import SessionLocal
from digitalcard.main import app
from digitalcard.models.account import LoginAudit, User, UserRole
from digitalcard.services.passwords import hash_password
from digitalcard.services.tokens import create_access_token, create_refresh_session

pytestmark = pytest.mark.anyio

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "Admin-Secure-2026!"
USER_EMAIL = "user@example.com"
USER_PASSWORD = "Member-Secure-2026!"
NEW_PASSWORD = "Changed-Secure-2026!"


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


def create_user(
    email: str = USER_EMAIL,
    password: str = USER_PASSWORD,
    role: UserRole = UserRole.USER,
) -> User:
    with SessionLocal() as db:
        user = User(
            email=email,
            display_name="Test User",
            password_hash=hash_password(password),
            role=role.value,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        db.expunge(user)
        return user


async def login(client: AsyncClient, email: str, password: str) -> dict[str, object]:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def authorization(session: dict[str, object]) -> dict[str, str]:
    return {"Authorization": f"Bearer {session['access_token']}"}


async def test_login_current_user_and_logout_immediately_revoke_access(
    client: AsyncClient,
) -> None:
    create_user()
    session = await login(client, USER_EMAIL, USER_PASSWORD)
    assert session["user"]["email"] == USER_EMAIL  # type: ignore[index]
    assert get_settings().refresh_cookie_name in client.cookies

    response = await client.get("/api/v1/auth/me", headers=authorization(session))
    assert response.status_code == 200

    response = await client.post("/api/v1/auth/logout")
    assert response.status_code == 204
    response = await client.get("/api/v1/auth/me", headers=authorization(session))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "session_revoked"

    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "refresh_required"


async def test_refresh_rotates_cookie_and_reuse_revokes_new_session(client: AsyncClient) -> None:
    create_user()
    original = await login(client, USER_EMAIL, USER_PASSWORD)
    cookie_name = get_settings().refresh_cookie_name
    old_cookie = client.cookies[cookie_name]

    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 200
    refreshed = response.json()
    assert client.cookies[cookie_name] != old_cookie

    response = await client.get("/api/v1/auth/me", headers=authorization(original))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "session_revoked"

    replay_transport = ASGITransport(app=app)
    async with AsyncClient(transport=replay_transport, base_url="http://test") as replay_client:
        replay_client.cookies.set(cookie_name, old_cookie, path="/api/v1/auth")
        response = await replay_client.post("/api/v1/auth/refresh")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "refresh_token_reused"

    response = await client.get("/api/v1/auth/me", headers=authorization(refreshed))
    assert response.status_code == 401
    assert response.json()["error"]["code"] in {"token_revoked", "session_revoked"}


async def test_password_change_invalidates_old_credentials_and_sessions(
    client: AsyncClient,
) -> None:
    create_user()
    session = await login(client, USER_EMAIL, USER_PASSWORD)
    response = await client.put(
        "/api/v1/auth/me/password",
        headers=authorization(session),
        json={"current_password": USER_PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert response.status_code == 204

    response = await client.get("/api/v1/auth/me", headers=authorization(session))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "token_revoked"
    response = await client.post(
        "/api/v1/auth/login", json={"email": USER_EMAIL, "password": USER_PASSWORD}
    )
    assert response.status_code == 401
    await login(client, USER_EMAIL, NEW_PASSWORD)


async def test_failed_logins_lock_account_and_are_audited(client: AsyncClient) -> None:
    create_user()
    for attempt in range(3):
        response = await client.post(
            "/api/v1/auth/login", json={"email": USER_EMAIL, "password": "Wrong-Password-1!"}
        )
        assert response.status_code == (429 if attempt == 2 else 401)

    response = await client.post(
        "/api/v1/auth/login", json={"email": USER_EMAIL, "password": USER_PASSWORD}
    )
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "account_locked"

    with SessionLocal() as db:
        audits = list(db.scalars(select(LoginAudit).where(LoginAudit.email == USER_EMAIL)))
        assert len(audits) == 4
        assert all(audit.success is False for audit in audits)
        assert all("password" not in audit.reason.lower() for audit in audits)


async def test_admin_can_create_disable_and_reset_user(client: AsyncClient) -> None:
    create_user(ADMIN_EMAIL, ADMIN_PASSWORD, UserRole.ADMIN)
    admin_session = await login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    response = await client.post(
        "/api/v1/admin/users",
        headers=authorization(admin_session),
        json={
            "email": USER_EMAIL,
            "display_name": "New User",
            "password": USER_PASSWORD,
            "role": "user",
        },
    )
    assert response.status_code == 201
    user_id = response.json()["id"]

    user_transport = ASGITransport(app=app)
    async with AsyncClient(transport=user_transport, base_url="http://test") as user_client:
        user_session = await login(user_client, USER_EMAIL, USER_PASSWORD)
        response = await user_client.get("/api/v1/admin/users", headers=authorization(user_session))
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "permission_denied"

        response = await client.patch(
            f"/api/v1/admin/users/{user_id}/status",
            headers=authorization(admin_session),
            json={"is_active": False},
        )
        assert response.status_code == 200
        response = await user_client.get("/api/v1/auth/me", headers=authorization(user_session))
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "account_disabled"

    response = await client.patch(
        f"/api/v1/admin/users/{user_id}/status",
        headers=authorization(admin_session),
        json={"is_active": True},
    )
    assert response.status_code == 200
    response = await client.post(
        f"/api/v1/admin/users/{user_id}/reset-password",
        headers=authorization(admin_session),
        json={"new_password": NEW_PASSWORD, "must_change_password": True},
    )
    assert response.status_code == 204
    reset_session = await login(client, USER_EMAIL, NEW_PASSWORD)
    assert reset_session["user"]["must_change_password"] is True  # type: ignore[index]


async def test_authentication_errors_are_distinct(client: AsyncClient) -> None:
    user = create_user()
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "auth_required"

    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-valid-token"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token"

    with SessionLocal() as db:
        stored_user = db.get(User, user.id)
        assert stored_user is not None
        _, refresh_session = create_refresh_session(
            db, stored_user, get_settings(), "127.0.0.1", "test"
        )
        db.commit()
        expired_token = create_access_token(
            stored_user, get_settings(), refresh_session.id, timedelta(seconds=-1)
        )
    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "token_expired"
