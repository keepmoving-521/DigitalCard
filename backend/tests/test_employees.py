from collections.abc import AsyncIterator
from urllib.parse import parse_qs, urlparse

import pytest
from httpx import ASGITransport, AsyncClient

from digitalcard.main import app
from test_tenancy import (
    bootstrap_two_companies,
    create_tenant_user,
    headers,
    sign_in,
)

pytestmark = pytest.mark.anyio


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as value:
        yield value


async def test_employee_tenant_isolation_uniqueness_and_filters(client: AsyncClient) -> None:
    _, _, _ = await bootstrap_two_companies(client)
    session_a = await sign_in(client, "admin-a@example.com")
    created = await client.post(
        "/api/v1/tenant/employees",
        headers=headers(session_a),
        json={
            "employee_no": "e-001",
            "name": "Alice",
            "phone": "+8613800000001",
            "email": "alice@example.com",
            "position": "Sales",
        },
    )
    assert created.status_code == 201, created.text
    employee_id = created.json()["id"]

    duplicate = await client.post(
        "/api/v1/tenant/employees",
        headers=headers(session_a),
        json={"employee_no": "E-001", "name": "Other"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "employee_no_exists"

    session_b = await sign_in(client, "admin-b@example.com")
    same_number = await client.post(
        "/api/v1/tenant/employees",
        headers=headers(session_b),
        json={"employee_no": "E-001", "name": "Bob"},
    )
    assert same_number.status_code == 201
    foreign = await client.get(
        f"/api/v1/tenant/employees/{employee_id}", headers=headers(session_b)
    )
    assert foreign.status_code == 404

    listed = await client.get(
        "/api/v1/tenant/employees?keyword=Alice&status=active&limit=1",
        headers=headers(session_a),
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["employee_no"] == "E-001"


async def test_csv_import_keeps_valid_rows_and_reports_invalid_rows(client: AsyncClient) -> None:
    _, _, _ = await bootstrap_two_companies(client)
    session = await sign_in(client, "admin-a@example.com")
    csv_body = (
        "employee_no,name,phone,email,position\n"
        "CSV-001,Valid,+8613900000001,valid@example.com,Engineer\n"
        "CSV-001,Duplicate,+8613900000002,duplicate@example.com,Engineer\n"
        "CSV-003,Bad phone,abc,bad@example.com,Engineer\n"
    )
    response = await client.post(
        "/api/v1/tenant/employees/import",
        headers={**headers(session), "Content-Type": "text/csv"},
        content=csv_body,
    )
    assert response.status_code == 200, response.text
    assert response.json()["succeeded"] == 1
    assert response.json()["failed"] == 2
    assert [row["row"] for row in response.json()["results"]] == [2, 3, 4]
    listed = await client.get("/api/v1/tenant/employees?keyword=CSV-001", headers=headers(session))
    assert listed.json()["total"] == 1


async def test_invitation_activation_and_employee_status_control_login(
    client: AsyncClient,
) -> None:
    _, _, _ = await bootstrap_two_companies(client)
    session = await sign_in(client, "admin-a@example.com")
    created = await client.post(
        "/api/v1/tenant/employees",
        headers=headers(session),
        json={
            "employee_no": "INV-001",
            "name": "Invited User",
            "email": "invited@example.com",
        },
    )
    employee_id = created.json()["id"]
    invited = await client.post(
        f"/api/v1/tenant/employees/{employee_id}/invite",
        headers=headers(session),
        json={"role": "employee"},
    )
    assert invited.status_code == 200, invited.text
    token = parse_qs(urlparse(invited.json()["invite_url"]).query)["token"][0]
    activated = await client.post(
        "/api/v1/auth/invitations/accept",
        json={"token": token, "password": "Welcome-Secure-2026!"},
    )
    assert activated.status_code == 204
    replay = await client.post(
        "/api/v1/auth/invitations/accept",
        json={"token": token, "password": "Welcome-Secure-2026!"},
    )
    assert replay.status_code == 400
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "invited@example.com", "password": "Welcome-Secure-2026!"},
    )
    assert login.status_code == 200

    disabled = await client.post(
        f"/api/v1/tenant/employees/{employee_id}/status",
        headers=headers(session),
        json={"status": "inactive"},
    )
    assert disabled.status_code == 200
    blocked = await client.post(
        "/api/v1/auth/login",
        json={"email": "invited@example.com", "password": "Welcome-Secure-2026!"},
    )
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "account_disabled"
    restored = await client.post(
        f"/api/v1/tenant/employees/{employee_id}/status",
        headers=headers(session),
        json={"status": "active"},
    )
    assert restored.status_code == 200
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "invited@example.com", "password": "Welcome-Secure-2026!"},
    )
    assert login.status_code == 200


async def test_self_edit_policy_and_public_inactive_visibility(client: AsyncClient) -> None:
    platform_session, company, _ = await bootstrap_two_companies(client)
    account = await create_tenant_user(
        client,
        platform_session,
        "profile@example.com",
        str(company["id"]),
        "employee",
    )
    admin_session = await sign_in(client, "admin-a@example.com")
    created = await client.post(
        "/api/v1/tenant/employees",
        headers=headers(admin_session),
        json={
            "employee_no": "SELF-001",
            "name": "Profile User",
            "email": "profile@example.com",
            "user_id": account["id"],
        },
    )
    employee_id = created.json()["id"]
    profile_session = await sign_in(client, "profile@example.com")
    updated = await client.patch(
        "/api/v1/tenant/employees/me",
        headers=headers(profile_session),
        json={"phone": "+8613700000001", "bio": "Hello"},
    )
    assert updated.status_code == 200
    controlled = await client.patch(
        "/api/v1/tenant/employees/me",
        headers=headers(profile_session),
        json={"department_id": "forbidden"},
    )
    assert controlled.status_code == 422

    await client.put(
        "/api/v1/tenant/company",
        headers=headers(admin_session),
        json={"employee_self_editable_fields": ["bio"]},
    )
    denied = await client.patch(
        "/api/v1/tenant/employees/me",
        headers=headers(profile_session),
        json={"phone": "+8613700000002"},
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "self_edit_not_allowed"

    await client.post(
        f"/api/v1/tenant/employees/{employee_id}/status",
        headers=headers(admin_session),
        json={"status": "inactive"},
    )
    public = await client.get(f"/api/v1/public/employees/{employee_id}")
    assert public.status_code == 404
    await client.put(
        "/api/v1/tenant/company",
        headers=headers(admin_session),
        json={"inactive_employee_visibility": "show_inactive"},
    )
    public = await client.get(f"/api/v1/public/employees/{employee_id}")
    assert public.status_code == 200
    assert public.json()["employment_status"] == "inactive"
