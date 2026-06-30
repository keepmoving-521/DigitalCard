from collections.abc import AsyncIterator

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


async def create_employee_profile(
    client: AsyncClient,
    admin_session: dict[str, object],
    employee_no: str,
    name: str,
    email: str,
    user_id: str,
) -> dict[str, object]:
    response = await client.post(
        "/api/v1/tenant/employees",
        headers=headers(admin_session),
        json={
            "employee_no": employee_no,
            "name": name,
            "email": email,
            "position": "顾问",
            "user_id": user_id,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def setup_employee(client: AsyncClient):  # type: ignore[no-untyped-def]
    platform, company, _ = await bootstrap_two_companies(client)
    account = await create_tenant_user(
        client, platform, "card-owner@example.com", str(company["id"]), "employee"
    )
    admin_session = await sign_in(client, "admin-a@example.com")
    employee = await create_employee_profile(
        client,
        admin_session,
        "CARD-001",
        "名片员工",
        "card-owner@example.com",
        str(account["id"]),
    )
    owner_session = await sign_in(client, "card-owner@example.com")
    return platform, company, admin_session, owner_session, employee


async def test_draft_changes_do_not_change_published_snapshot(client: AsyncClient) -> None:
    _, _, _, owner_session, _ = await setup_employee(client)
    response = await client.patch(
        "/api/v1/tenant/cards/me",
        headers=headers(owner_session),
        json={"headline": "第一版名片"},
    )
    assert response.status_code == 200, response.text
    published = await client.post("/api/v1/tenant/cards/me/publish", headers=headers(owner_session))
    assert published.status_code == 200, published.text
    card_id = published.json()["id"]
    assert published.json()["status"] == "published"

    public = await client.get(f"/api/v1/public/cards/{card_id}")
    assert public.status_code == 200
    assert public.json()["data"]["headline"] == "第一版名片"

    edited = await client.patch(
        "/api/v1/tenant/cards/me",
        headers=headers(owner_session),
        json={"headline": "尚未发布的第二版"},
    )
    assert edited.json()["status"] == "published"
    assert edited.json()["has_unpublished_changes"] is True
    public = await client.get(f"/api/v1/public/cards/{card_id}")
    assert public.json()["data"]["headline"] == "第一版名片"
    preview = await client.get("/api/v1/tenant/cards/me/preview", headers=headers(owner_session))
    assert preview.json()["data"]["headline"] == "尚未发布的第二版"


async def test_template_lock_and_cross_employee_permissions(client: AsyncClient) -> None:
    platform, company, admin_session, owner_session, owner = await setup_employee(client)
    template = await client.put(
        "/api/v1/tenant/card-template",
        headers=headers(admin_session),
        json={
            "name": "企业标准模板",
            "theme_color": "#123456",
            "logo_url": "https://example.com/logo.png",
            "module_order": ["profile", "bio", "contact", "social"],
            "locked_fields": ["theme_color", "logo_url", "module_order"],
            "employee_editable_fields": [
                "display_name",
                "headline",
                "avatar_url",
                "bio",
                "phone",
                "email",
                "wechat",
                "website",
                "socials",
                "theme_color",
            ],
        },
    )
    assert template.status_code == 200, template.text
    locked = await client.patch(
        "/api/v1/tenant/cards/me",
        headers=headers(owner_session),
        json={"theme_color": "#abcdef"},
    )
    assert locked.status_code == 403
    assert locked.json()["error"]["code"] == "card_field_locked"

    other_account = await create_tenant_user(
        client, platform, "other-card@example.com", str(company["id"]), "employee"
    )
    other = await create_employee_profile(
        client,
        admin_session,
        "CARD-002",
        "其他员工",
        "other-card@example.com",
        str(other_account["id"]),
    )
    forbidden = await client.patch(
        f"/api/v1/tenant/cards/{other['id']}",
        headers=headers(owner_session),
        json={"headline": "越权编辑"},
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "permission_denied"

    managed = await client.patch(
        f"/api/v1/tenant/cards/{owner['id']}",
        headers=headers(admin_session),
        json={"headline": "管理员维护的职位"},
    )
    assert managed.status_code == 200
    preview = await client.get(
        f"/api/v1/tenant/cards/{owner['id']}/preview", headers=headers(admin_session)
    )
    assert preview.json()["data"]["theme_color"] == "#123456"
    assert preview.json()["data"]["headline"] == "管理员维护的职位"


async def test_publish_validation_offline_and_republish(client: AsyncClient) -> None:
    _, _, _, owner_session, _ = await setup_employee(client)
    cleared = await client.patch(
        "/api/v1/tenant/cards/me",
        headers=headers(owner_session),
        json={"phone": None, "email": None},
    )
    assert cleared.status_code == 200
    invalid = await client.post("/api/v1/tenant/cards/me/publish", headers=headers(owner_session))
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "card_publish_validation_failed"
    assert "phone_or_email" in invalid.json()["error"]["details"]["missing"]

    await client.patch(
        "/api/v1/tenant/cards/me",
        headers=headers(owner_session),
        json={"email": "card-owner@example.com", "headline": "可发布版本"},
    )
    published = await client.post("/api/v1/tenant/cards/me/publish", headers=headers(owner_session))
    card_id = published.json()["id"]
    offline = await client.post("/api/v1/tenant/cards/me/offline", headers=headers(owner_session))
    assert offline.json()["status"] == "offline"
    assert (await client.get(f"/api/v1/public/cards/{card_id}")).status_code == 404

    republished = await client.post(
        "/api/v1/tenant/cards/me/publish", headers=headers(owner_session)
    )
    assert republished.json()["status"] == "published"
    assert (await client.get(f"/api/v1/public/cards/{card_id}")).status_code == 200
