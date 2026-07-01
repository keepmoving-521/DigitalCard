from datetime import timedelta
from time import perf_counter
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import insert, select

from digitalcard.core.time import utc_now
from digitalcard.db.session import SessionLocal
from digitalcard.main import app
from digitalcard.models.analytics import BusinessEvent
from digitalcard.models.card import DigitalCard
from test_analytics import setup_analytics
from test_tenancy import headers

pytestmark = pytest.mark.anyio


async def test_large_dashboard_query_does_not_block_public_event_path() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        admin, _, _, card_id = await setup_analytics(client)

        with SessionLocal() as db:
            card = db.scalar(select(DigitalCard).where(DigitalCard.id == card_id))
            assert card is not None
            now = utc_now()
            db.execute(
                insert(BusinessEvent),
                [
                    {
                        "id": str(uuid4()),
                        "company_id": card.company_id,
                        "employee_id": card.employee_id,
                        "card_id": card.id,
                        "event_type": "view",
                        "event_category": "view",
                        "channel": f"channel-{index % 8}",
                        "visitor_hash": f"visitor-{index % 4000}",
                        "dedupe_key": f"performance:{index}",
                        "is_bot": False,
                        "is_internal": False,
                        "details": {},
                        "occurred_at": now - timedelta(seconds=index % 86400),
                        "created_at": now,
                    }
                    for index in range(10_000)
                ],
            )
            db.commit()

        dashboard_started = perf_counter()
        dashboard = await client.get(
            "/api/v1/tenant/analytics/dashboard?ranking_dimension=channel",
            headers=headers(admin),
        )
        dashboard_elapsed = perf_counter() - dashboard_started
        assert dashboard.status_code == 200, dashboard.text
        assert dashboard.json()["metrics"]["views"] == 10_000
        assert dashboard_elapsed < 3.0

        public_started = perf_counter()
        event = await client.post(
            f"/api/v1/public/cards/{card_id}/events",
            json={
                "event_type": "view",
                "visitor_id": "visitor-after-dashboard",
                "source": "performance-check",
            },
        )
        public_elapsed = perf_counter() - public_started
        assert event.status_code == 201, event.text
        assert public_elapsed < 1.0
