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


async def setup_crm(client: AsyncClient):  # type: ignore[no-untyped-def]
    platform, company, _ = await bootstrap_two_companies(client)
    first_user = await create_tenant_user(
        client, platform, "crm-sales-1@example.com", str(company["id"]), "sales"
    )
    second_user = await create_tenant_user(
        client, platform, "crm-sales-2@example.com", str(company["id"]), "sales"
    )
    admin = await sign_in(client, "admin-a@example.com")
    first_employee = await create_employee_profile(
        client,
        admin,
        "CRM-SALE-1",
        "销售甲",
        "crm-sales-1@example.com",
        str(first_user["id"]),
    )
    second_employee = await create_employee_profile(
        client,
        admin,
        "CRM-SALE-2",
        "销售乙",
        "crm-sales-2@example.com",
        str(second_user["id"]),
    )
    card = await client.get("/api/v1/tenant/cards/me", headers=headers(admin))
    published = await client.post("/api/v1/tenant/cards/me/publish", headers=headers(admin))
    assert card.status_code == published.status_code == 200
    return (
        admin,
        await sign_in(client, "crm-sales-1@example.com"),
        await sign_in(client, "crm-sales-2@example.com"),
        first_employee,
        second_employee,
        published.json()["id"],
    )


async def create_and_assign_lead(
    client: AsyncClient,
    admin: dict[str, object],
    card_id: str,
    employee_id: str,
    contact: str,
) -> str:
    created = await client.post(
        f"/api/v1/public/cards/{card_id}/leads",
        json={
            "name": f"客户-{contact[-4:]}",
            "contact": contact,
            "demand": "CRM 测试需求",
            "privacy_agreed": True,
            "source": "crm_test",
        },
    )
    assert created.status_code == 201, created.text
    lead_id = created.json()["id"]
    assigned = await client.post(
        f"/api/v1/tenant/leads/{lead_id}/assign",
        headers=headers(admin),
        json={"employee_id": employee_id},
    )
    assert assigned.status_code == 200
    return lead_id


async def test_convert_follow_up_opportunity_history_and_transfer(client: AsyncClient) -> None:
    admin, sales_one, sales_two, first_employee, second_employee, card_id = await setup_crm(client)
    lead_id = await create_and_assign_lead(
        client, admin, card_id, first_employee["id"], "13800003333"
    )
    converted = await client.post(
        f"/api/v1/tenant/leads/{lead_id}/convert",
        headers=headers(sales_one),
        json={"tags": ["重点", "线上"]},
    )
    assert converted.status_code == 201, converted.text
    customer_id = converted.json()["id"]

    timeline = await client.get(
        f"/api/v1/tenant/customers/{customer_id}/timeline", headers=headers(sales_one)
    )
    assert [item["event_type"] for item in timeline.json()] == [
        "source_visit",
        "lead_converted",
    ]
    assert timeline.json()[1]["details"]["lead_id"] == lead_id
    assert timeline.json()[1]["details"]["source"] == "crm_test"

    follow_up = await client.post(
        f"/api/v1/tenant/customers/{customer_id}/follow-ups",
        headers=headers(sales_one),
        json={
            "method": "phone",
            "content": "已沟通产品方案",
            "next_follow_up_at": "2026-07-10T09:00:00",
        },
    )
    assert follow_up.status_code == 201
    stages = await client.get("/api/v1/tenant/opportunity-stages", headers=headers(sales_one))
    assert stages.status_code == 200
    initial, proposal = stages.json()[0:2]
    opportunity = await client.post(
        f"/api/v1/tenant/customers/{customer_id}/opportunities",
        headers=headers(sales_one),
        json={
            "title": "数字名片项目",
            "stage_id": initial["id"],
            "expected_amount": "88000.00",
            "expected_close_date": "2026-08-01",
        },
    )
    assert opportunity.status_code == 201, opportunity.text
    changed = await client.patch(
        f"/api/v1/tenant/opportunities/{opportunity.json()['id']}",
        headers=headers(sales_one),
        json={"stage_id": proposal["id"]},
    )
    assert changed.status_code == 200
    history = await client.get(
        f"/api/v1/tenant/opportunities/{opportunity.json()['id']}/history",
        headers=headers(sales_one),
    )
    assert [item["to_stage_id"] for item in history.json()] == [initial["id"], proposal["id"]]
    assert all(item["actor_user_id"] for item in history.json())

    transferred = await client.post(
        f"/api/v1/tenant/customers/{customer_id}/transfer",
        headers=headers(admin),
        json={"employee_id": second_employee["id"]},
    )
    assert transferred.status_code == 200
    assert (
        await client.get(
            f"/api/v1/tenant/customers/{customer_id}", headers=headers(sales_one)
        )
    ).status_code == 404
    assert (
        await client.get(
            f"/api/v1/tenant/customers/{customer_id}", headers=headers(sales_two)
        )
    ).status_code == 200
    funnel = await client.get(
        "/api/v1/tenant/opportunities/funnel/summary", headers=headers(sales_two)
    )
    assert next(item for item in funnel.json()["items"] if item["stage_id"] == proposal["id"])[
        "count"
    ] == 1


async def test_merge_preview_and_merge_preserve_related_records(client: AsyncClient) -> None:
    admin, _, _, first_employee, _, card_id = await setup_crm(client)
    customer_ids: list[str] = []
    for contact in ("13800004444", "13900005555"):
        lead_id = await create_and_assign_lead(
            client, admin, card_id, first_employee["id"], contact
        )
        converted = await client.post(
            f"/api/v1/tenant/leads/{lead_id}/convert",
            headers=headers(admin),
            json={"owner_employee_id": first_employee["id"], "tags": [contact[-4:]]},
        )
        assert converted.status_code == 201
        customer_ids.append(converted.json()["id"])
    target_id, source_id = customer_ids
    await client.post(
        f"/api/v1/tenant/customers/{source_id}/contacts",
        headers=headers(admin),
        json={
            "name": "采购负责人",
            "contact_type": "wechat",
            "contact_value": "buyer-wechat",
        },
    )
    await client.post(
        f"/api/v1/tenant/customers/{source_id}/follow-ups",
        headers=headers(admin),
        json={"method": "meeting", "content": "现场沟通"},
    )
    stages = await client.get("/api/v1/tenant/opportunity-stages", headers=headers(admin))
    await client.post(
        f"/api/v1/tenant/customers/{source_id}/opportunities",
        headers=headers(admin),
        json={"title": "待合并商机", "stage_id": stages.json()[0]["id"], "expected_amount": 1000},
    )
    preview = await client.post(
        f"/api/v1/tenant/customers/{target_id}/merge-preview",
        headers=headers(admin),
        json={"source_customer_id": source_id},
    )
    assert preview.status_code == 200
    assert "primary_contact" in preview.json()["conflicts"]
    assert preview.json()["moved_counts"] == {
        "contacts": 2,
        "follow_ups": 1,
        "opportunities": 1,
    }
    merged = await client.post(
        f"/api/v1/tenant/customers/{target_id}/merge",
        headers=headers(admin),
        json={"source_customer_id": source_id},
    )
    assert merged.status_code == 200
    detail = await client.get(
        f"/api/v1/tenant/customers/{target_id}", headers=headers(admin)
    )
    assert len(detail.json()["contacts"]) == 3
    assert len(
        (
            await client.get(
                f"/api/v1/tenant/customers/{target_id}/follow-ups", headers=headers(admin)
            )
        ).json()
    ) == 1
    assert len(
        (
            await client.get(
                f"/api/v1/tenant/customers/{target_id}/opportunities",
                headers=headers(admin),
            )
        ).json()
    ) == 1
    assert (
        await client.get(f"/api/v1/tenant/customers/{source_id}", headers=headers(admin))
    ).status_code == 404
