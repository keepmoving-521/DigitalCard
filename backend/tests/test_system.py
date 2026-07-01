import pytest
from httpx import ASGITransport, AsyncClient, Response

from digitalcard.main import app

pytestmark = pytest.mark.anyio


async def request(path: str) -> Response:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


async def test_health_check() -> None:
    response = await request("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "DigitalCard API",
        "version": "1.4.0",
        "environment": "test",
    }
    assert response.headers["X-Request-ID"]


async def test_readiness_check() -> None:
    response = await request("/api/v1/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "ok"}


async def test_openapi_document_is_available() -> None:
    response = await request("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["version"] == "1.4.0"


async def test_not_found_uses_unified_error_shape() -> None:
    response = await request("/missing")
    body = response.json()["error"]
    assert response.status_code == 404
    assert body["code"] == "not_found"
    assert body["request_id"] == response.headers["X-Request-ID"]
