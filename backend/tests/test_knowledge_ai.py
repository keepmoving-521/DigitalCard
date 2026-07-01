import pytest
from httpx import ASGITransport, AsyncClient

from digitalcard.main import app
from test_tenancy import bootstrap_two_companies, headers, sign_in

pytestmark = pytest.mark.anyio


async def enable_ai(client: AsyncClient, session: dict[str, object], daily_limit: int = 100):
    response = await client.put(
        "/api/v1/tenant/ai/config",
        headers=headers(session),
        json={
            "enabled": True,
            "public_qa_enabled": True,
            "sales_assistant_enabled": True,
            "welcome_message": "您好",
            "system_prompt": "仅根据企业授权内容回答",
            "daily_limit": daily_limit,
        },
    )
    assert response.status_code == 200, response.text


async def test_public_ai_is_tenant_isolated_cites_sources_and_forgets_disabled_content() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        _, _, _ = await bootstrap_two_companies(client)
        admin_a = await sign_in(client, "admin-a@example.com")
        admin_b = await sign_in(client, "admin-b@example.com")
        await enable_ai(client, admin_a)
        await enable_ai(client, admin_b)
        source_a = await client.post(
            "/api/v1/tenant/knowledge/sources",
            headers=headers(admin_a),
            json={
                "source_type": "faq",
                "title": "交付周期",
                "content": "Company A 标准交付周期是七个工作日。",
                "is_authorized": True,
            },
        )
        await client.post(
            "/api/v1/tenant/knowledge/sources",
            headers=headers(admin_b),
            json={
                "source_type": "faq",
                "title": "保密答案",
                "content": "Company B 专属暗号是蓝鲸。",
                "is_authorized": True,
            },
        )
        answer = await client.post(
            "/api/v1/public/ai/company-a/ask", json={"question": "标准交付周期是多久？"}
        )
        assert answer.status_code == 200, answer.text
        assert answer.json()["uncertain"] is False
        assert "七个工作日" in answer.json()["answer"]
        assert answer.json()["citations"][0]["source_id"] == source_a.json()["id"]
        cross_tenant = await client.post(
            "/api/v1/public/ai/company-a/ask", json={"question": "蓝鲸暗号是什么？"}
        )
        assert cross_tenant.json()["uncertain"] is True
        assert "蓝鲸" not in cross_tenant.json()["answer"]

        disabled = await client.post(
            f"/api/v1/tenant/knowledge/sources/{source_a.json()['id']}/disable",
            headers=headers(admin_a),
        )
        assert disabled.json()["status"] == "disabled"
        after_disable = await client.post(
            "/api/v1/public/ai/company-a/ask", json={"question": "标准交付周期是多久？"}
        )
        assert after_disable.json()["uncertain"] is True
        feedback = await client.post(
            f"/api/v1/public/ai/interactions/{after_disable.json()['interaction_id']}/feedback",
            json={"rating": -1, "comment": "需要人工"},
        )
        assert feedback.status_code == 200
        stats = await client.get("/api/v1/tenant/ai/stats", headers=headers(admin_a))
        assert stats.json()["negative_feedback"] == 1
        assert stats.json()["uncertain"] >= 2


async def test_ai_drafts_require_confirmation_and_usage_limit_is_enforced() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        _, _, _ = await bootstrap_two_companies(client)
        admin = await sign_in(client, "admin-a@example.com")
        await enable_ai(client, admin, daily_limit=1)
        draft = await client.post(
            "/api/v1/tenant/ai/drafts",
            headers=headers(admin),
            json={"draft_type": "follow_up_suggestion", "context": "客户关注交付时间"},
        )
        assert draft.status_code == 200
        assert draft.json()["requires_confirmation"] is True
        assert "AI 建议草稿" in draft.json()["content"]
        first = await client.post(
            "/api/v1/public/ai/company-a/ask", json={"question": "没有资料的问题"}
        )
        assert first.status_code == 200
        assert first.json()["uncertain"] is True
        limited = await client.post(
            "/api/v1/public/ai/company-a/ask", json={"question": "再问一个问题"}
        )
        assert limited.status_code == 429
