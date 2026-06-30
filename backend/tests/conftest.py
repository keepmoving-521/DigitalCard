import os

import pytest

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-at-least-32-characters")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
