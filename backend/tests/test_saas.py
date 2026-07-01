from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from digitalcard.core.time import utc_now
from digitalcard.db.session import SessionLocal
from digitalcard.main import app
from digitalcard.models.saas import SubscriptionStatus, TenantSubscription
from test_tenancy import bootstrap_two_companies, headers, sign_in

pytestmark = pytest.mark.anyio


async def test_plan_quota_expiry_and_existing_data_protection() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        platform, company, _ = await bootstrap_two_companies(client)
        admin = await sign_in(client, "admin-a@example.com")
        created = await client.post(
            "/api/v1/tenant/employees",
            headers=headers(admin),
            json={"employee_no": "LIMIT-1", "name": "存量员工", "email": "existing@example.com"},
        )
        assert created.status_code == 201, created.text
        plan = await client.post(
            "/api/v1/platform/saas/plans",
            headers=headers(platform),
            json={
                "code": "small",
                "name": "小型版",
                "employee_limit": 1,
                "card_limit": 1,
                "storage_limit_bytes": 1024,
                "is_active": True,
            },
        )
        assert plan.status_code == 201, plan.text
        changed = await client.put(
            f"/api/v1/platform/saas/tenants/{company['id']}/subscription",
            headers=headers(platform),
            json={
                "plan_id": plan.json()["id"],
                "expires_at": (utc_now() + timedelta(days=30)).isoformat(),
                "note": "套餐调整",
            },
        )
        assert changed.status_code == 200
        assert "employees" in changed.json()["warnings"]
        blocked = await client.post(
            "/api/v1/tenant/employees",
            headers=headers(admin),
            json={"employee_no": "LIMIT-2", "name": "新增员工", "email": "new@example.com"},
        )
        assert blocked.status_code == 409
        assert blocked.json()["error"]["code"] == "quota_exceeded"
        existing = await client.get("/api/v1/tenant/employees", headers=headers(admin))
        assert existing.status_code == 200
        assert existing.json()["total"] == 1

        expired = await client.put(
            f"/api/v1/platform/saas/tenants/{company['id']}/subscription",
            headers=headers(platform),
            json={
                "plan_id": plan.json()["id"],
                "expires_at": (utc_now() - timedelta(minutes=1)).isoformat(),
            },
        )
        assert expired.json()["status"] == "expired"
        blocked = await client.post(
            "/api/v1/tenant/employees",
            headers=headers(admin),
            json={"employee_no": "LIMIT-3", "name": "到期新增", "email": "expired@example.com"},
        )
        assert blocked.status_code == 409
        assert (
            await client.get("/api/v1/tenant/employees", headers=headers(admin))
        ).status_code == 200


async def test_support_authorization_logs_and_cancellation_cooling_period() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        platform, company, _ = await bootstrap_two_companies(client)
        grant = await client.post(
            "/api/v1/platform/saas/support-grants",
            headers=headers(platform),
            json={
                "company_id": company["id"],
                "granted_to_user_id": platform["user"]["id"],
                "reason": "协助排查企业配额异常",
                "expires_at": (utc_now() + timedelta(hours=1)).isoformat(),
            },
        )
        assert grant.status_code == 201, grant.text
        denied = await client.get(
            f"/api/v1/platform/saas/support/tenants/{company['id']}/overview",
            headers={**headers(platform), "X-Support-Grant-Token": "invalid"},
        )
        assert denied.status_code == 403
        overview = await client.get(
            f"/api/v1/platform/saas/support/tenants/{company['id']}/overview",
            headers={**headers(platform), "X-Support-Grant-Token": grant.json()["token"]},
        )
        assert overview.status_code == 200
        logs = await client.get("/api/v1/platform/saas/logs", headers=headers(platform))
        assert any(item["action"] == "support.tenant_overview_accessed" for item in logs.json())

        cancel = await client.post(
            f"/api/v1/platform/saas/tenants/{company['id']}/cancel",
            headers=headers(platform),
            json={"confirmation": company["code"], "cooling_days": 1},
        )
        assert cancel.status_code == 200
        assert cancel.json()["status"] == "cancel_pending"
        confirm = await client.post(
            f"/api/v1/platform/saas/tenants/{company['id']}/cancel/confirm",
            headers=headers(platform),
        )
        assert confirm.status_code == 409
        with SessionLocal() as db:
            subscription = db.scalar(
                select(TenantSubscription).where(TenantSubscription.company_id == company["id"])
            )
            assert subscription is not None
            subscription.cancel_effective_at = utc_now() - timedelta(seconds=1)
            db.commit()
        confirmed = await client.post(
            f"/api/v1/platform/saas/tenants/{company['id']}/cancel/confirm",
            headers=headers(platform),
        )
        assert confirmed.status_code == 200
        assert confirmed.json()["status"] == SubscriptionStatus.CANCELLED.value
