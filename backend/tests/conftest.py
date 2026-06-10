from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.models import User

_test_session_factory: async_sessionmaker[AsyncSession] | None = None


@pytest_asyncio.fixture(autouse=True)
async def sqlite_test_database() -> AsyncIterator[None]:
    global _test_session_factory

    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    _test_session_factory = session_factory

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_session, None)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
        await engine.dispose()
        _test_session_factory = None


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    assert _test_session_factory is not None
    async with _test_session_factory() as test_session:
        yield test_session


__all__ = ["User"]
