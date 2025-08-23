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
    global _session_factory
    if _session_factory is None:
        get_engine()
    assert _session_factory is not None
    async with _session_factory() as session:
        yield session


