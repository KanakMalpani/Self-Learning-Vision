from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings


def async_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if database_url.startswith("sqlite+aiosqlite://"):
        return database_url
    if database_url.startswith("sqlite://"):
        return database_url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    return database_url


async_engine = None
AsyncSessionLocal = None


def get_async_sessionmaker():
    global async_engine, AsyncSessionLocal
    if AsyncSessionLocal is None:
        async_engine = create_async_engine(async_database_url(settings.database_url), future=True)
        AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False, autoflush=False)
    return AsyncSessionLocal


async def get_async_db() -> AsyncIterator[AsyncSession]:
    sessionmaker = get_async_sessionmaker()
    async with sessionmaker() as session:
        yield session
