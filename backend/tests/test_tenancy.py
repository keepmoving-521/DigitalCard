from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from digitalcard.db.session import SessionLocal
from digitalcard.main import app
from digitalcard.models.account import User, UserRole
from digitalcard.services.passwords import hash_password

pytestmark = pytest.mark.anyio

PLATFORM_EMAIL = "platform@example.com"
PASSWORD = "Tenant-Secure-2026!"


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


def create_platform_admin() -> None:
    with SessionLocal() as db:
        db.add(
            User(
                email=PLATFORM_EMAIL,
                display_name="Platform Admin",
                password_hash=hash_password(PASSWORD),
                role=UserRole.PLATFORM_ADMIN.value,
            )
        )
        db.commit()


async def sign_in(client: AsyncClient, email: str) -> dict[str, object]:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return response.json()


def headers(session: dict[str, object]) -> dict[str, str]:
    return {"Authorization": f"Bearer {session['access_token']}"}


async def create_company(
    client: AsyncClient, platform_session: dict[str, object], code: str, name: str
) -> dict[str, object]:
    response = await client.post(
        "/api/v1/platform/companies",
        headers=headers(platform_session),
        json={"code": code, "name": name},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_tenant_user(
    client: AsyncClient,
    platform_session: dict[str, object],
    email: str,
    company_id: str,
    role: str,
    department_id: str | None = None,
) -> dict[str, object]:
    response = await client.post(
        "/api/v1/admin/users",
        headers=headers(platform_session),
        json={
            "email": email,
            "display_name": email.split("@", maxsplit=1)[0],
            "password": PASSWORD,
            "role": role,
            "company_id": company_id,
            "department_id": department_id,
            "must_change_password": False,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def bootstrap_two_companies(client: AsyncClient):  # type: ignore[no-untyped-def]
    create_platform_admin()
    platform_session = await sign_in(client, PLATFORM_EMAIL)
    company_a = await create_company(client, platform_session, "company-a", "Company A")
    company_b = await create_company(client, platform_session, "company-b", "Company B")
    await create_tenant_user(
        client,
        platform_session,
        "admin-a@example.com",
        str(company_a["id"]),
        "company_admin",
    )
    await create_tenant_user(
        client,
        platform_session,
        "admin-b@example.com",
        str(company_b["id"]),
        "company_admin",
    )
    return platform_session, company_a, company_b


async def test_departments_are_isolated_and_codes_only_unique_inside_tenant(
    client: AsyncClient,
) -> None:
    _, _, _ = await bootstrap_two_companies(client)
    transport_a = ASGITransport(app=app)
    transport_b = ASGITransport(app=app)
    async with (
        AsyncClient(transport=transport_a, base_url="http://test") as client_a,
        AsyncClient(transport=transport_b, base_url="http://test") as client_b,
    ):
        session_a = await sign_in(client_a, "admin-a@example.com")
        session_b = await sign_in(client_b, "admin-b@example.com")
        response_a = await client_a.post(
            "/api/v1/tenant/departments",
            headers=headers(session_a),
            json={"code": "sales", "name": "Sales A"},
        )
        response_b = await client_b.post(
            "/api/v1/tenant/departments",
            headers=headers(session_b),
            json={"code": "sales", "name": "Sales B"},
        )
        assert response_a.status_code == response_b.status_code == 201

        foreign_id = response_b.json()["id"]
        response = await client_a.patch(
            f"/api/v1/tenant/departments/{foreign_id}",
            headers=headers(session_a),
            json={"name": "Cross-tenant write"},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "department_not_found"

        response = await client_a.get("/api/v1/tenant/departments", headers=headers(session_a))
        assert [item["name"] for item in response.json()] == ["Sales A"]


async def test_role_permissions_apply_immediately_and_platform_boundary_is_enforced(
    client: AsyncClient,
) -> None:
    platform_session, company_a, _ = await bootstrap_two_companies(client)
    await create_tenant_user(
        client,
        platform_session,
        "content@example.com",
        str(company_a["id"]),
        "content_admin",
    )
    admin_transport = ASGITransport(app=app)
    content_transport = ASGITransport(app=app)
    async with (
        AsyncClient(transport=admin_transport, base_url="http://test") as admin_client,
        AsyncClient(transport=content_transport, base_url="http://test") as content_client,
    ):
        admin_session = await sign_in(admin_client, "admin-a@example.com")
        content_session = await sign_in(content_client, "content@example.com")

        response = await content_client.post(
            "/api/v1/tenant/departments",
            headers=headers(content_session),
            json={"code": "content", "name": "Content"},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "permission_denied"

        response = await admin_client.put(
            "/api/v1/tenant/roles/content_admin/permissions",
            headers=headers(admin_session),
            json={
                "permissions": [
                    "company.read",
                    "department.read",
                    "department.create",
                    "content.manage",
                ]
            },
        )
        assert response.status_code == 200
        response = await content_client.post(
            "/api/v1/tenant/departments",
            headers=headers(content_session),
            json={"code": "content", "name": "Content"},
        )
        assert response.status_code == 201

        response = await admin_client.get(
            "/api/v1/platform/companies", headers=headers(admin_session)
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "permission_denied"

        response = await admin_client.get("/api/v1/tenant/audits", headers=headers(admin_session))
        assert response.status_code == 200
        assert any(item["action"] == "role.permissions_updated" for item in response.json())


async def test_department_with_active_employee_cannot_be_disabled(client: AsyncClient) -> None:
    platform_session, company_a, _ = await bootstrap_two_companies(client)
    admin_transport = ASGITransport(app=app)
    async with AsyncClient(transport=admin_transport, base_url="http://test") as admin_client:
        admin_session = await sign_in(admin_client, "admin-a@example.com")
        response = await admin_client.post(
            "/api/v1/tenant/departments",
            headers=headers(admin_session),
            json={"code": "engineering", "name": "Engineering"},
        )
        department_id = response.json()["id"]

        employee = await create_tenant_user(
            client,
            platform_session,
            "engineer@example.com",
            str(company_a["id"]),
            "employee",
            department_id,
        )
        response = await admin_client.post(
            f"/api/v1/tenant/departments/{department_id}/status",
            headers=headers(admin_session),
            json={"is_active": False},
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "department_not_empty"
        assert response.json()["error"]["details"]["employee_count"] == 1

        response = await client.patch(
            f"/api/v1/admin/users/{employee['id']}/status",
            headers=headers(platform_session),
            json={"is_active": False},
        )
        assert response.status_code == 200
        response = await admin_client.post(
            f"/api/v1/tenant/departments/{department_id}/status",
            headers=headers(admin_session),
            json={"is_active": False},
        )
        assert response.status_code == 200
        assert response.json()["is_active"] is False


async def test_suspending_company_immediately_blocks_tenant_access(client: AsyncClient) -> None:
    platform_session, company_a, _ = await bootstrap_two_companies(client)
    tenant_transport = ASGITransport(app=app)
    async with AsyncClient(transport=tenant_transport, base_url="http://test") as tenant_client:
        tenant_session = await sign_in(tenant_client, "admin-a@example.com")
        response = await client.patch(
            f"/api/v1/platform/companies/{company_a['id']}/status",
            headers=headers(platform_session),
            json={"status": "suspended"},
        )
        assert response.status_code == 200

        response = await tenant_client.get(
            "/api/v1/tenant/company", headers=headers(tenant_session)
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "company_suspended"


async def test_company_profile_changes_are_scoped_and_audited(client: AsyncClient) -> None:
    _, _, _ = await bootstrap_two_companies(client)
    tenant_transport = ASGITransport(app=app)
    async with AsyncClient(transport=tenant_transport, base_url="http://test") as tenant_client:
        tenant_session = await sign_in(tenant_client, "admin-a@example.com")
        response = await tenant_client.put(
            "/api/v1/tenant/company",
            headers=headers(tenant_session),
            json={"name": "Company A Updated", "contact_phone": "400-800-2026"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Company A Updated"

        response = await tenant_client.get("/api/v1/tenant/audits", headers=headers(tenant_session))
        actions = [item["action"] for item in response.json()]
        assert "company.profile_updated" in actions
        assert all(
            item["company_id"] == response.json()[0]["company_id"] for item in response.json()
        )
