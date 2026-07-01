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


async def setup_analytics(client: AsyncClient):  # type: ignore[no-untyped-def]
    platform, company, _ = await bootstrap_two_companies(client)
    first_user = await create_tenant_user(
        client, platform, "analytics-one@example.com", str(company["id"]), "sales"
    )
    second_user = await create_tenant_user(
        client, platform, "analytics-two@example.com", str(company["id"]), "sales"
    )
    admin = await sign_in(client, "admin-a@example.com")
    await create_employee_profile(
        client,
        admin,
        "ANA-001",
        "分析销售一",
        "analytics-one@example.com",
        str(first_user["id"]),
    )
    await create_employee_profile(
        client,
        admin,
        "ANA-002",
        "分析销售二",
        "analytics-two@example.com",
        str(second_user["id"]),
    )
    first = await sign_in(client, "analytics-one@example.com")
    second = await sign_in(client, "analytics-two@example.com")
    await client.get("/api/v1/tenant/cards/me", headers=headers(first))
    published = await client.post("/api/v1/tenant/cards/me/publish", headers=headers(first))
    assert published.status_code == 200
    return admin, first, second, published.json()["id"]


async def record_event(
    client: AsyncClient,
    card_id: str,
    event_type: str,
    visitor: str,
    source: str = "campaign",
    user_agent: str = "Mozilla/5.0",
):  # type: ignore[no-untyped-def]
    return await client.post(
        f"/api/v1/public/cards/{card_id}/events",
        headers={"User-Agent": user_agent},
        json={"event_type": event_type, "visitor_id": visitor, "source": source},
    )


async def test_dashboard_filters_deduplicates_and_enforces_personal_scope(
    client: AsyncClient,
) -> None:
    admin, first, second, card_id = await setup_analytics(client)
    first_view = await record_event(client, card_id, "view", "visitor-normal-001")
    duplicate = await record_event(client, card_id, "view", "visitor-normal-001")
    assert first_view.status_code == 201
    assert duplicate.status_code == 200
    assert duplicate.json()["recorded"] is False
    await record_event(client, card_id, "share_copy", "visitor-normal-001")
    await record_event(client, card_id, "call", "visitor-normal-001")
    await record_event(client, card_id, "view", "visitor-bot-00001", user_agent="Googlebot/2.1")
    await record_event(client, card_id, "view", "visitor-internal", source="internal")

    lead = await client.post(
        f"/api/v1/public/cards/{card_id}/leads",
        json={
            "name": "分析客户",
            "contact": "analytics-customer@example.com",
            "demand": "分析转化",
            "privacy_agreed": True,
            "source": "campaign",
        },
    )
    assert lead.status_code == 201
    await client.post(f"/api/v1/tenant/leads/{lead.json()['id']}/claim", headers=headers(first))
    customer = await client.post(
        f"/api/v1/tenant/leads/{lead.json()['id']}/convert",
        headers=headers(first),
        json={"tags": []},
    )
    assert customer.status_code == 201

    dashboard = await client.get(
        "/api/v1/tenant/analytics/dashboard?ranking_dimension=channel",
        headers=headers(first),
    )
    assert dashboard.status_code == 200, dashboard.text
    body = dashboard.json()
    assert body["scope"] == "employee"
    assert body["metrics"] == {
        "views": 1,
        "unique_visitors": 1,
        "shares": 1,
        "clicks": 1,
        "leads": 1,
        "conversions": 1,
        "view_to_lead_rate": 1.0,
        "lead_to_customer_rate": 1.0,
    }
    assert body["filtered_bot_events"] == 1
    assert body["filtered_internal_events"] == 1
    assert body["last_updated_at"]
    assert any(item["lead_id"] == lead.json()["id"] for item in body["samples"])
    assert any(item["dimension_id"] == "campaign" for item in body["ranking"])

    empty = await client.get("/api/v1/tenant/analytics/dashboard", headers=headers(second))
    assert empty.status_code == 200
    assert empty.json()["metrics"]["views"] == 0
    admin_view = await client.get("/api/v1/tenant/analytics/dashboard", headers=headers(admin))
    assert admin_view.json()["scope"] == "company"
    assert admin_view.json()["metrics"]["leads"] == 1

    denied_export = await client.get("/api/v1/tenant/analytics/export", headers=headers(first))
    assert denied_export.status_code == 403
    exported = await client.get("/api/v1/tenant/analytics/export", headers=headers(admin))
    assert exported.status_code == 200
    assert exported.content.startswith(b"\xef\xbb\xbf")
    assert "lead_submitted" in exported.text
