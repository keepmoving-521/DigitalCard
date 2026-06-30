import os

import pytest

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-at-least-32-characters")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("LOGIN_MAX_ATTEMPTS", "3")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def reset_database():  # type: ignore[no-untyped-def]
    from digitalcard.db.base import Base
    from digitalcard.db.session import engine
    from digitalcard.models import LoginAudit, RefreshSession, User  # noqa: F401

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)
