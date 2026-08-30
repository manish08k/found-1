"""Shared pytest fixtures."""
import asyncio
import os
import time
import pytest
from unittest.mock import AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession

# Patch env vars before any module-level settings are loaded
os.environ.setdefault("APP_SECRET_KEY", "test-secret-key-for-pytest-32chars!!")
os.environ.setdefault("CREDENTIAL_ENCRYPTION_KEY", "test-cred-key-for-pytest-32chars!!")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("FRONTEND_URL", "http://localhost:3000")


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_db():
    return AsyncMock(spec=AsyncSession)


# ── In-memory Redis substitute for tests that don't have a real Redis ─────────

class _FakeRedis:
    """Minimal async Redis stub supporting the operations used in auth middleware."""

    def __init__(self):
        self._store: dict = {}   # key → value
        self._expiry: dict = {}  # key → expiry epoch

    def _expired(self, key: str) -> bool:
        exp = self._expiry.get(key)
        return exp is not None and time.time() > exp

    def _clean(self, key: str) -> None:
        if self._expired(key):
            self._store.pop(key, None)
            self._expiry.pop(key, None)

    async def get(self, key: str):
        self._clean(key)
        return self._store.get(key)

    async def set(self, key: str, value, ex: int | None = None):
        self._store[key] = value
        if ex is not None:
            self._expiry[key] = time.time() + ex

    async def incr(self, key: str) -> int:
        self._clean(key)
        val = int(self._store.get(key, 0)) + 1
        self._store[key] = str(val)
        return val

    async def expire(self, key: str, seconds: int):
        if key in self._store:
            self._expiry[key] = time.time() + seconds

    async def ttl(self, key: str) -> int:
        self._clean(key)
        exp = self._expiry.get(key)
        if exp is None:
            return -1
        return max(0, int(exp - time.time()))

    async def delete(self, *keys: str):
        for k in keys:
            self._store.pop(k, None)
            self._expiry.pop(k, None)

    async def aclose(self):
        pass


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    """Replace the module-level _redis singleton with an in-memory fake.

    ``autouse=True`` means every test gets a fresh, isolated Redis stub
    automatically — no real Redis required, no cross-test state leakage.
    """
    import api.middleware.auth as _auth_mod
    stub = _FakeRedis()
    monkeypatch.setattr(_auth_mod, "_redis", stub)
    return stub
