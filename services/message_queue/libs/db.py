"""Database engine and session utilities for async SQLAlchemy.

This module centralizes engine/session creation so that all components share a
single, lazily initialized async engine. It also handles common URL quirks
(e.g., ``postgres://`` vs ``postgresql://``) and provides a simple
``asynccontextmanager`` for sessions.

Why this exists:
- Ensure a consistent, well-tuned engine across producers/workers/scripts
- Avoid duplicated URL parsing/normalization logic scattered across modules

How to use:
- Call ``get_engine()`` once to initialize the engine (optional; ``get_session``
  will also initialize it on first use).
- Use ``get_session()`` as an async context manager for DB work:

    Example:
        >>> from libs.db import get_session
        >>> async with get_session() as session:
        ...     await session.execute("SELECT 1")
        ...     await session.commit()
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from typing import Any
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # type: ignore

from libs.config import Settings


_engine: Any = None
_session_factory: Any = None


def get_engine() -> Any:
    """Return a process-wide async SQLAlchemy engine, creating it if needed.

    The engine is created lazily from either ``DATABASE_URL`` or the
    Supabase URL in ``Settings``. URLs of the form ``postgres://`` or
    ``postgresql://`` are normalized to ``postgresql+asyncpg://`` for the
    ``asyncpg`` driver.

    Returns:
        Any: A SQLAlchemy async engine instance.

    Example:
        >>> engine = get_engine()
        >>> str(engine.url).startswith("postgresql+asyncpg://")
        True
    """
    global _engine, _session_factory
    if _engine is None:
        settings = Settings()
        # Support postgres:// and postgresql:// URLs. For asyncpg, prefix with postgresql+asyncpg
        db_url = os.getenv("DATABASE_URL", "") or settings.supabase_url.replace("postgresql://", "postgresql+asyncpg://")
        if not db_url.startswith("postgresql+asyncpg://"):
            if db_url.startswith("postgresql://"):
                db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
            elif db_url.startswith("postgres://"):
                db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
        _engine = create_async_engine(db_url, pool_pre_ping=True)
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


@asynccontextmanager
async def get_session() -> AsyncIterator[Any]:
    """Yield an async SQLAlchemy session bound to the shared engine.

    Initializes the engine/session factory on first use. Sessions are created
    with ``expire_on_commit=False`` to avoid automatic attribute expiration and
    to keep ergonomics simple for small scripts/services.

    Yields:
        AsyncIterator[Any]: A SQLAlchemy ``AsyncSession`` instance.

    Example:
        >>> async with get_session() as session:
        ...     await session.commit()
    """
    global _session_factory
    if _session_factory is None:
        get_engine()
    assert _session_factory is not None
    async with _session_factory() as session:
        yield session


