"""Poison message detection.

Tracks repeated failures for the same ``dedup_key`` and triggers quarantine
once a configurable threshold is reached. Counters are stored in Postgres via
SQLAlchemy and read during failure handling to decide whether to quarantine.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select  # type: ignore
from sqlalchemy.exc import SQLAlchemyError  # type: ignore

from libs.config import Settings
from libs.db import get_session
from libs.orm_models import PoisonCounter


def _threshold() -> int:
    """Return the configured poison threshold with a safe default."""
    try:
        return Settings().poison_threshold
    except Exception:
        return 3


async def increment_failure(org_id: str, dedup_key: str) -> int:
    """Increment and return the current failure count for a message key.

    Returns 1 on first failure, and best-effort values on errors.
    """
    try:
        async with get_session() as session:
            res = await session.execute(
                select(PoisonCounter).where(
                    PoisonCounter.org_id == org_id, PoisonCounter.dedup_key == dedup_key
                )
            )
            row = res.scalar_one_or_none()
            if row is None:
                session.add(PoisonCounter(org_id=org_id, dedup_key=dedup_key, count=1))
                await session.commit()
                return 1
            row.count += 1
            await session.commit()
            return row.count
    except SQLAlchemyError:
        return 1


async def should_quarantine(org_id: str, dedup_key: str) -> bool:
    """Return True when the failure count is at or above the threshold."""
    try:
        async with get_session() as session:
            res = await session.execute(
                select(PoisonCounter.count).where(
                    PoisonCounter.org_id == org_id, PoisonCounter.dedup_key == dedup_key
                )
            )
            current = res.scalar_one_or_none() or 0
        return current >= _threshold()
    except SQLAlchemyError:
        return False


