import pytest
from httpx import ASGITransport, AsyncClient

from digitalcard.main import app
from test_analytics import setup_analytics
from test_tenancy import headers, sign_in

pytestmark = pytest.mark.anyio


async def test_credentials_scopes_tenant_isolation_idempotency_and_webhook_failures() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        admin, _, _, card_id = await setup_analytics(client)
        admin_b = await sign_in(client, "admin-b@example.com")
        await client.get("/api/v1/tenant/cards/me", headers=headers(admin_b))
        card_b = await client.post("/api/v1/tenant/cards/me/publish", headers=headers(admin_b))
        assert card_b.status_code == 200

        created = await client.post(
            "/api/v1/tenant/open/apps",
            headers=headers(admin),
            json={"name": "CRM 集成", "scopes": ["leads.write"], "rate_limit_per_minute": 10},
        )
        assert created.status_code == 201, created.text
        credential = created.json()
        assert credential["app_secret"]
        listed = await client.get("/api/v1/tenant/open/apps", headers=headers(admin))
        assert "app_secret" not in listed.json()[0]
        app_headers = {"X-App-Key": credential["app_key"], "X-App-Secret": credential["app_secret"]}

        webhook = await client.post(
            f"/api/v1/tenant/open/apps/{credential['id']}/webhooks",
            headers=headers(admin),
            json={"target_url": "http://127.0.0.1:9/webhook", "events": ["lead.created"]},
        )
        assert webhook.status_code == 201
        assert webhook.json()["signing_secret"]

        payload = {
            "card_id": card_id,
            "name": "开放客户",
            "contact": "open@example.com",
            "source": "partner",
            "idempotency_key": "partner-event-0001",
        }
        first = await client.post("/api/v1/open/v1/leads", headers=app_headers, json=payload)
        second = await client.post("/api/v1/open/v1/leads", headers=app_headers, json=payload)
        assert first.status_code == 201, first.text
        assert second.status_code == 201 or second.status_code == 200
        assert first.json()["id"] == second.json()["id"]
        deliveries = await client.get("/api/v1/tenant/open/deliveries", headers=headers(admin))
        assert len(deliveries.json()) == 1
        delivery = deliveries.json()[0]
        assert delivery["signature"]
        assert delivery["idempotency_key"].endswith(first.json()["id"])
        retried = await client.post(
            f"/api/v1/tenant/open/deliveries/{delivery['id']}/retry", headers=headers(admin)
        )
        assert retried.status_code == 200
        assert retried.json()["attempts"] == 1
        assert retried.json()["error"]

        cross = await client.post(
            "/api/v1/open/v1/leads",
            headers=app_headers,
            json={
                **payload,
                "card_id": card_b.json()["id"],
                "idempotency_key": "partner-event-cross",
            },
        )
        assert cross.status_code == 404
        forbidden_scope = await client.patch(
            "/api/v1/open/v1/customers/missing", headers=app_headers, json={"name": "不能修改"}
        )
        assert forbidden_scope.status_code == 403

        rotated = await client.post(
            f"/api/v1/tenant/open/apps/{credential['id']}/rotate", headers=headers(admin)
        )
        assert rotated.json()["app_secret"] != credential["app_secret"]
        old_denied = await client.post(
            "/api/v1/open/v1/leads",
            headers=app_headers,
            json={**payload, "idempotency_key": "partner-event-old"},
        )
        assert old_denied.status_code == 401


async def test_message_preferences_and_read_all() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        admin, _, _, _ = await setup_analytics(client)
        preferences = await client.get(
            "/api/v1/tenant/notifications/preferences", headers=headers(admin)
        )
        assert preferences.status_code == 200
        updated = await client.put(
            "/api/v1/tenant/notifications/preferences",
            headers=headers(admin),
            json={"new_lead": False, "follow_up_due": True, "quota_warning": False},
        )
        assert updated.json()["new_lead"] is False
        read_all = await client.post(
            "/api/v1/tenant/notifications/read-all", headers=headers(admin)
        )
        assert read_all.status_code == 204
