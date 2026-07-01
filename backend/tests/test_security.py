import pytest
from httpx import ASGITransport, AsyncClient

from digitalcard.core.config import get_settings
from digitalcard.main import app

pytestmark = pytest.mark.anyio


async def test_security_headers_are_present() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert response.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"


def test_production_settings_require_non_local_browser_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "a-production-secret-that-is-long-enough")
    get_settings.cache_clear()
    with pytest.raises(ValueError, match="localhost"):
        get_settings()
    get_settings.cache_clear()
