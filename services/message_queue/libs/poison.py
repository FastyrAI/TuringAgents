"""Poison message detection.

Tracks repeated failures of the same dedup_key and quarantines after a
threshold. Uses Supabase to persist counters (simple implementation).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select  # type: ignore
from sqlalchemy.exc import SQLAlchemyError  # type: ignore

from libs.config import Settings
from libs.db import get_session
from libs.orm_models import PoisonCounter


def _threshold() -> int:
    try:
        return Settings().poison_threshold
    except Exception:
        return 3


async def increment_failure(org_id: str, dedup_key: str) -> int:
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


