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


async def test_create_share_capture_and_follow_up_main_flow(client: AsyncClient) -> None:
    platform, company, _ = await bootstrap_two_companies(client)
    sales_user = await create_tenant_user(
        client, platform, "mvp-sales@example.com", str(company["id"]), "sales"
    )
    admin = await sign_in(client, "admin-a@example.com")
    await client.post(
        "/api/v1/tenant/departments",
        headers=headers(admin),
        json={"code": "MVP-SALES", "name": "销售部"},
    )
    await create_employee_profile(
        client,
        admin,
        "MVP-001",
        "首批销售",
        "mvp-sales@example.com",
        str(sales_user["id"]),
    )
    sales = await sign_in(client, "mvp-sales@example.com")
    saved = await client.patch(
        "/api/v1/tenant/cards/me",
        headers=headers(sales),
        json={"headline": "企业顾问", "phone": "13800006666"},
    )
    assert saved.status_code == 200
    published = await client.post("/api/v1/tenant/cards/me/publish", headers=headers(sales))
    assert published.status_code == 200
    card_id = published.json()["id"]
    public = await client.get(f"/api/v1/public/cards/{card_id}?source=mvp_acceptance")
    assert public.status_code == 200

    submitted = await client.post(
        f"/api/v1/public/cards/{card_id}/leads",
        json={
            "name": "试用客户",
            "contact": "customer@example.com",
            "demand": "希望安排产品演示",
            "privacy_agreed": True,
            "source": "mvp_acceptance",
        },
    )
    assert submitted.status_code == 201
    lead_id = submitted.json()["id"]
    claimed = await client.post(f"/api/v1/tenant/leads/{lead_id}/claim", headers=headers(sales))
    assert claimed.status_code == 200
    customer = await client.post(
        f"/api/v1/tenant/leads/{lead_id}/convert",
        headers=headers(sales),
        json={"tags": ["首批试用"]},
    )
    assert customer.status_code == 201
    followed = await client.post(
        f"/api/v1/tenant/customers/{customer.json()['id']}/follow-ups",
        headers=headers(sales),
        json={"method": "email", "content": "已发送产品演示安排"},
    )
    assert followed.status_code == 201
    timeline = await client.get(
        f"/api/v1/tenant/customers/{customer.json()['id']}/timeline",
        headers=headers(sales),
    )
    assert {event["event_type"] for event in timeline.json()} >= {
        "source_visit",
        "lead_converted",
        "follow_up",
    }
    monitoring = await client.get("/api/v1/tenant/monitoring", headers=headers(admin))
    assert monitoring.status_code == 200
    assert monitoring.json()["card_publish"]["attempts"] >= 1
    assert monitoring.json()["lead_submit"]["attempts"] >= 1
    assert monitoring.json()["average_first_response_minutes"] is not None
