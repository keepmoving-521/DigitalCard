from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from digitalcard.main import app
from test_cards import create_employee_profile
from test_tenancy import bootstrap_two_companies, create_tenant_user, headers, sign_in

pytestmark = pytest.mark.anyio


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as value:
        yield value


async def setup_leads(client: AsyncClient):  # type: ignore[no-untyped-def]
    platform, company, _ = await bootstrap_two_companies(client)
    sales_account = await create_tenant_user(
        client, platform, "sales-lead@example.com", str(company["id"]), "sales"
    )
    other_account = await create_tenant_user(
        client, platform, "other-sales@example.com", str(company["id"]), "sales"
    )
    admin = await sign_in(client, "admin-a@example.com")
    sales_employee = await create_employee_profile(
        client,
        admin,
        "SALE-LEAD-1",
        "销售一",
        "sales-lead@example.com",
        str(sales_account["id"]),
    )
    await create_employee_profile(
        client,
        admin,
        "SALE-LEAD-2",
        "销售二",
        "other-sales@example.com",
        str(other_account["id"]),
    )
    card = await client.get("/api/v1/tenant/cards/me", headers=headers(admin))
    published = await client.post("/api/v1/tenant/cards/me/publish", headers=headers(admin))
    assert card.status_code == published.status_code == 200
    return (
        admin,
        await sign_in(client, "sales-lead@example.com"),
        await sign_in(client, "other-sales@example.com"),
        sales_employee,
        published.json()["id"],
    )


async def test_privacy_duplicate_assignment_and_sales_visibility(client: AsyncClient) -> None:
    admin, sales, other_sales, sales_employee, card_id = await setup_leads(client)
    rejected = await client.post(
        f"/api/v1/public/cards/{card_id}/leads",
        json={"name": "访客", "contact": "13800001111", "privacy_agreed": False},
    )
    assert rejected.status_code == 422

    payload = {
        "name": "访客",
        "contact": "138 0000 1111",
        "demand": "希望了解产品",
        "privacy_agreed": True,
        "source": "wechat",
    }
    created = await client.post(f"/api/v1/public/cards/{card_id}/leads", json=payload)
    assert created.status_code == 201, created.text
    assert created.json()["duplicate"] is False
    duplicate = await client.post(
        f"/api/v1/public/cards/{card_id}/leads", json={**payload, "contact": "13800001111"}
    )
    assert duplicate.status_code == 201
    assert duplicate.json()["duplicate"] is True
    assert duplicate.json()["id"] == created.json()["id"]

    admin_list = await client.get("/api/v1/tenant/leads", headers=headers(admin))
    assert admin_list.status_code == 200
    assert admin_list.json()["items"][0]["duplicate_count"] == 1
    assigned = await client.post(
        f"/api/v1/tenant/leads/{created.json()['id']}/assign",
        headers=headers(admin),
        json={"employee_id": sales_employee["id"]},
    )
    assert assigned.status_code == 200, assigned.text

    visible = await client.get("/api/v1/tenant/leads", headers=headers(sales))
    hidden = await client.get("/api/v1/tenant/leads", headers=headers(other_sales))
    assert [item["id"] for item in visible.json()["items"]] == [created.json()["id"]]
    assert hidden.json()["items"] == []
    assert (
        await client.get(
            f"/api/v1/tenant/leads/{created.json()['id']}", headers=headers(other_sales)
        )
    ).status_code == 404

    claimed = await client.post(
        f"/api/v1/tenant/leads/{created.json()['id']}/claim", headers=headers(sales)
    )
    assert claimed.status_code == 200
    assert claimed.json()["status"] == "claimed"
    invalid = await client.post(
        f"/api/v1/tenant/leads/{created.json()['id']}/status",
        headers=headers(sales),
        json={"status": "invalid"},
    )
    assert invalid.status_code == 200

    notifications = await client.get("/api/v1/tenant/notifications", headers=headers(sales))
    assert notifications.status_code == 200
    assert notifications.json()["unread_count"] == 1
    notification_id = notifications.json()["items"][0]["id"]
    read = await client.post(
        f"/api/v1/tenant/notifications/{notification_id}/read", headers=headers(sales)
    )
    assert read.status_code == 204
