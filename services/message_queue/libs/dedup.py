"""Idempotency helpers backed by SQLAlchemy (async).

Store a (org_id, dedup_key) pair with a unique constraint to prevent
double-processing of the same logical message.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.exc import IntegrityError

from libs.db import get_session
from libs.orm_models import IdempotencyKey


def compute_dedup_key(message: dict[str, Any]) -> str:
    """Return the dedup key for a message (default: message_id)."""
    return str(message.get("dedup_key") or message.get("message_id"))


async def mark_and_check(org_id: str, dedup_key: str) -> bool:
    """Insert the dedup key; return True if first time, False if duplicate."""
    try:
        async with get_session() as session:
            session.add(IdempotencyKey(org_id=org_id, dedup_key=dedup_key))
            await session.commit()
            return True
    except IntegrityError:
        return False
    except Exception:
        # On unexpected errors, allow processing (fail-open) to avoid blocking
        return True


