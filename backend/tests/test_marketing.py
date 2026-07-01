from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from digitalcard.core.time import utc_now
from digitalcard.main import app
from test_analytics import setup_analytics
from test_tenancy import headers

pytestmark = pytest.mark.anyio


async def create_form(client: AsyncClient, admin: dict[str, object]):
    response = await client.post(
        "/api/v1/tenant/marketing/forms",
        headers=headers(admin),
        json={
            "name": "新品试用报名",
            "fields": [
                {"key": "name", "label": "姓名", "type": "text", "required": True},
                {"key": "contact", "label": "联系方式", "type": "text", "required": True},
                {"key": "demand", "label": "需求", "type": "textarea", "required": False},
            ],
            "privacy_notice": "仅用于本次活动联系",
            "success_message": "报名成功",
            "is_active": True,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_campaign(
    client: AsyncClient,
    admin: dict[str, object],
    form_id: str,
    card_id: str,
    owner_id: str,
    slug: str,
    start_delta: int = -1,
    end_delta: int = 1,
    capacity: int | None = 10,
):
    now = utc_now()
    response = await client.post(
        "/api/v1/tenant/marketing/campaigns",
        headers=headers(admin),
        json={
            "form_id": form_id,
            "name": slug,
            "slug": slug,
            "description": "活动说明",
            "card_id": card_id,
            "product_id": None,
            "owner_employee_id": owner_id,
            "channel": "poster",
            "starts_at": (now + timedelta(hours=start_delta)).isoformat(),
            "ends_at": (now + timedelta(hours=end_delta)).isoformat(),
            "capacity": capacity,
        },
    )
    assert response.status_code == 201, response.text
    campaign = response.json()
    published = await client.post(
        f"/api/v1/tenant/marketing/campaigns/{campaign['id']}/publish", headers=headers(admin)
    )
    assert published.status_code == 200, published.text
    return campaign


async def test_campaign_state_snapshot_duplicate_export_and_conversion() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        admin, sales, _, card_id = await setup_analytics(client)
        employee = (await client.get("/api/v1/tenant/employees/me", headers=headers(sales))).json()
        form = await create_form(client, admin)
        campaign = await create_campaign(
            client, admin, form["id"], card_id, employee["id"], "summer-demo", capacity=1
        )

        public = await client.get("/api/v1/public/campaigns/summer-demo")
        assert public.status_code == 200
        assert public.json()["state"] == "open"
        submitted = await client.post(
            "/api/v1/public/campaigns/summer-demo/submissions",
            json={
                "values": {
                    "name": "王客户",
                    "contact": "customer@example.com",
                    "demand": "希望试用",
                },
                "privacy_agreed": True,
                "source": "wechat",
                "website": "",
            },
        )
        assert submitted.status_code == 201, submitted.text
        assert submitted.json()["duplicate"] is False
        full = await client.get("/api/v1/public/campaigns/summer-demo")
        assert full.json()["state"] == "full"
        blocked = await client.post(
            "/api/v1/public/campaigns/summer-demo/submissions",
            json={
                "values": {"name": "另一位", "contact": "other@example.com"},
                "privacy_agreed": True,
            },
        )
        assert blocked.status_code == 409

        updated_form = {
            **{
                key: form[key]
                for key in ("name", "fields", "privacy_notice", "success_message", "is_active")
            },
            "fields": form["fields"]
            + [
                {
                    "key": "company",
                    "label": "公司",
                    "type": "text",
                    "required": False,
                    "options": [],
                }
            ],
        }
        changed = await client.put(
            f"/api/v1/tenant/marketing/forms/{form['id']}",
            headers=headers(admin),
            json=updated_form,
        )
        assert changed.json()["revision"] == 2
        listing = await client.get(
            f"/api/v1/tenant/marketing/campaigns/{campaign['id']}/submissions",
            headers=headers(admin),
        )
        item = listing.json()["items"][0]
        assert item["form_revision"] == 1
        assert all(field["key"] != "company" for field in item["form_snapshot"]["fields"])

        denied = await client.get(
            f"/api/v1/tenant/marketing/campaigns/{campaign['id']}/export", headers=headers(sales)
        )
        assert denied.status_code == 403
        exported = await client.get(
            f"/api/v1/tenant/marketing/campaigns/{campaign['id']}/export", headers=headers(admin)
        )
        assert exported.status_code == 200
        assert "customer@example.com" in exported.text
        converted = await client.post(
            f"/api/v1/tenant/marketing/submissions/{item['id']}/convert", headers=headers(admin)
        )
        assert converted.status_code == 200
        listing = await client.get(
            f"/api/v1/tenant/marketing/campaigns/{campaign['id']}/submissions",
            headers=headers(admin),
        )
        assert listing.json()["items"][0]["lead_id"] == converted.json()["lead_id"]
        stats = await client.get(
            f"/api/v1/tenant/marketing/campaigns/{campaign['id']}/stats", headers=headers(admin)
        )
        assert stats.json()["conversion_rate"] == 1


async def test_campaign_rejects_not_started_ended_spam_and_missing_consent() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        admin, sales, _, card_id = await setup_analytics(client)
        employee = (await client.get("/api/v1/tenant/employees/me", headers=headers(sales))).json()
        form = await create_form(client, admin)
        await create_campaign(
            client, admin, form["id"], card_id, employee["id"], "future-demo", 1, 2
        )
        await create_campaign(
            client, admin, form["id"], card_id, employee["id"], "ended-demo", -2, -1
        )
        assert (
            await client.post(
                "/api/v1/public/campaigns/future-demo/submissions",
                json={"values": {"name": "A", "contact": "a@example.com"}, "privacy_agreed": True},
            )
        ).status_code == 409
        assert (
            await client.post(
                "/api/v1/public/campaigns/ended-demo/submissions",
                json={"values": {"name": "A", "contact": "a@example.com"}, "privacy_agreed": True},
            )
        ).status_code == 409
        assert (
            await client.post(
                "/api/v1/public/campaigns/future-demo/submissions",
                json={"values": {"name": "A", "contact": "a@example.com"}, "privacy_agreed": False},
            )
        ).status_code == 422
