"""Shared pytest fixtures."""
import asyncio
import os
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
