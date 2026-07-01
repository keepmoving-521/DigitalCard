from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from digitalcard.main import app
from test_tenancy import bootstrap_two_companies, headers, sign_in

pytestmark = pytest.mark.anyio


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as value:
        yield value


async def test_onboarding_guides_company_to_first_published_card(client: AsyncClient) -> None:
    await bootstrap_two_companies(client)
    admin = await sign_in(client, "admin-a@example.com")
    initial = await client.get("/api/v1/tenant/onboarding", headers=headers(admin))
    assert initial.status_code == 200
    assert initial.json()["completed"] is False
    assert [step["code"] for step in initial.json()["steps"]] == [
        "company",
        "department",
        "employee",
        "card",
    ]
    company = await client.get("/api/v1/tenant/company", headers=headers(admin))
    updated = await client.put(
        "/api/v1/tenant/company",
        headers=headers(admin),
        json={
            "name": company.json()["name"],
            "contact_email": "owner@example.com",
        },
    )
    assert updated.status_code == 200
    department = await client.post(
        "/api/v1/tenant/departments",
        headers=headers(admin),
        json={"code": "START", "name": "起步部门"},
    )
    assert department.status_code == 201
    card = await client.get("/api/v1/tenant/cards/me", headers=headers(admin))
    assert card.status_code == 200
    published = await client.post("/api/v1/tenant/cards/me/publish", headers=headers(admin))
    assert published.status_code == 200
    completed = await client.get("/api/v1/tenant/onboarding", headers=headers(admin))
    assert completed.json()["completed"] is True
