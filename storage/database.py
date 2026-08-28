"""Async SQLAlchemy session factories — primary (read/write) + optional read replica."""
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,
    echo=settings.DEBUG,
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

# Read replica: if DATABASE_URL_REPLICA isn't set, this just reuses the
# primary engine/session factory, so every route that asks for a read-only
# session still works with zero replica configured — it just doesn't get
# the offload benefit until one is added (k8s/00-namespace-config.yml has
# the placeholder env var).
if settings.DATABASE_URL_REPLICA:
    replica_engine = create_async_engine(
        settings.DATABASE_URL_REPLICA,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        pool_pre_ping=True,
        echo=settings.DEBUG,
    )
    AsyncSessionReplica = async_sessionmaker(replica_engine, expire_on_commit=False)
else:
    replica_engine = engine
    AsyncSessionReplica = AsyncSessionLocal


async def get_db() -> AsyncSession:
    """Primary session — use for any request that writes."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db_read() -> AsyncSession:
    """
    Read-only session, routed to the replica when one is configured.
    Use this for list/history/dashboard endpoints (execution history,
    workflow listing, DLQ browsing) that don't need read-your-writes
    consistency within the same request. Never commit writes through this
    session — the replica is not writable and it will just error.
    """
    async with AsyncSessionReplica() as session:
        yield session


@asynccontextmanager
async def db_context():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
