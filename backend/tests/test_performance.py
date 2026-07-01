import time

import pytest
from httpx import ASGITransport, AsyncClient

from digitalcard.main import app

pytestmark = pytest.mark.anyio


async def test_health_endpoint_local_p95_baseline() -> None:
    durations: list[float] = []
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for _ in range(50):
            started = time.perf_counter()
            response = await client.get("/api/v1/health")
            durations.append((time.perf_counter() - started) * 1000)
            assert response.status_code == 200
    durations.sort()
    p95 = durations[int(len(durations) * 0.95) - 1]
    assert p95 < 100
