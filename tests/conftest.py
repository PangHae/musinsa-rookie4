from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.database import get_db
from app.main import app
from app.models import Base
from app.seed import seed_database

TEST_DB_URL = (
    f"mysql+aiomysql://{settings.DB_USER}:{settings.DB_PASSWORD}"
    f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}_test"
    f"?charset=utf8mb4"
)

# Track whether DB has been set up in this process
_db_initialized = False


async def _ensure_db_setup():
    """Ensure DB tables and seed data exist (idempotent)."""
    global _db_initialized
    if _db_initialized:
        return

    engine = create_async_engine(
        TEST_DB_URL, pool_size=5, max_overflow=5, isolation_level="READ_COMMITTED"
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        await seed_database(session)

    await engine.dispose()
    _db_initialized = True


@pytest_asyncio.fixture
async def db() -> AsyncGenerator[AsyncSession]:
    await _ensure_db_setup()
    engine = create_async_engine(
        TEST_DB_URL, pool_size=20, max_overflow=10, isolation_level="READ_COMMITTED"
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    await _ensure_db_setup()

    engine = create_async_engine(
        TEST_DB_URL, pool_size=20, max_overflow=10, isolation_level="READ_COMMITTED"
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db() -> AsyncGenerator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.pop(get_db, None)
    await engine.dispose()
