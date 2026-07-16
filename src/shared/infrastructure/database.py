"""Database session factory and connection management.

Provides:
- AsyncSession factory configured from env vars
- Health check for database connectivity
- Session dependency for FastAPI
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models.

    All models across all engines inherit from this.
    """
    pass


def get_database_url() -> str:
    """Get database URL from environment variable.

    Checks GHOS_DB_URL_ASYNC first (for async engines), then GHOS_DB_URL.

    Returns:
        Database URL string for async SQLAlchemy engine.
    """
    return os.getenv(
        "GHOS_DB_URL_ASYNC",
        os.getenv(
            "GHOS_DB_URL",
            "postgresql+asyncpg://ghos:ghos@localhost:5432/ghos",
        ),
    )


def get_pool_size() -> int:
    """Get connection pool size from environment.

    Returns:
        Pool size (default: 10).
    """
    return int(os.getenv("GHOS_DB_POOL_SIZE", "10"))


_db_url = get_database_url()
_engine_kwargs = {
    "pool_size": get_pool_size(),
    "max_overflow": 5,
    "pool_pre_ping": True,
    "echo": os.getenv("GHOS_DB_ECHO", "").lower() == "true",
}

# SQLite needs special connect args and schema translation
if _db_url.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
    _engine_kwargs["execution_options"] = {"schema_translate_map": {"identity": None}}

engine = create_async_engine(_db_url, **_engine_kwargs)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions.

    Yields:
        AsyncSession: Database session that auto-closes on request completion.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def unit_of_work() -> AsyncIterator[AsyncSession]:
    """Context manager for manual transaction control.

    Usage:
        async with unit_of_work() as session:
            session.add(user)
            await session.flush()
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_database_health() -> bool:
    """Check if the database is reachable.

    Returns:
        True if database responds, False otherwise.
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
