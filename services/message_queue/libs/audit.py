"""Thin async wrappers for writing audit records using SQLAlchemy (async).

All writes are best-effort to avoid impacting the processing loop.
"""
from __future__ import annotations

import asyncio
from typing import Any, Optional

from sqlalchemy.dialects.postgresql import insert

from libs.config import ENVIRONMENT
from libs.db import get_session
from libs.orm_models import Message, MessageEvent, DLQMessage


def _apply_redaction(obj: dict[str, Any]) -> dict[str, Any]:
    # Simple redaction policy by environment
    if ENVIRONMENT == "production":
        redacted = dict(obj)
        if "payload" in redacted:
            redacted["payload"] = {"redacted": True}
        if "details" in redacted:
            redacted["details"] = {"redacted": True}
        return redacted
    return obj


async def _insert_event(payload: dict[str, Any]) -> None:
    try:
        async with get_session() as session:
            await session.execute(MessageEvent.__table__.insert().values(**payload))
            await session.commit()
    except Exception:
        return


async def record_message_event(event: dict[str, Any] | "MessageEventRecord") -> None:
    """Insert a lifecycle event into `message_events`.

    Accepts either a plain dict or a `MessageEventRecord` instance.
    """
    """Write a message lifecycle event to Supabase (table: message_events)."""
    from libs.models import MessageEventRecord

    payload = event.model_dump() if isinstance(event, MessageEventRecord) else event
    if ENVIRONMENT == "production" and "details" in payload:
        payload = {**payload, "details": {"redacted": True}}
    await _insert_event(payload)


async def record_dlq_message(entry: dict[str, Any] | "DLQMessageRecord") -> None:
    """Insert a DLQ row into `dlq_messages`.

    Accepts either a plain dict or a `DLQMessageRecord` instance.
    """
    """Write a DLQ entry to Supabase (table: dlq_messages)."""
    from libs.models import DLQMessageRecord

    payload = entry.model_dump() if isinstance(entry, DLQMessageRecord) else entry
    if ENVIRONMENT == "production":
        payload = {**payload, "original_message": {"redacted": True}, "error": {"redacted": True}}
    try:
        async with get_session() as session:
            await session.execute(DLQMessage.__table__.insert().values(**payload))
            await session.commit()
    except Exception:
        return


async def upsert_message(record: dict[str, Any] | "MessageRecord") -> None:
    """Upsert a row into `messages` keyed by `message_id`.

    Accepts either a plain dict or a `MessageRecord` instance.
    """
    """Upsert a message record in Supabase (table: messages)."""
    from libs.models import MessageRecord

    payload = record.model_dump() if isinstance(record, MessageRecord) else record
    if ENVIRONMENT == "production" and "payload" in payload:
        payload = {**payload, "payload": {"redacted": True}}
    try:
        async with get_session() as session:
            stmt = insert(Message).values(**payload)
            do_update_stmt = stmt.on_conflict_do_update(
                index_elements=[Message.__table__.c.message_id],
                set_={
                    "status": stmt.excluded.status,
                    "payload": stmt.excluded.payload,
                    "updated_at": stmt.excluded.updated_at,
                    "priority": stmt.excluded.priority,
                    "type": stmt.excluded.type,
                },
            )
            await session.execute(do_update_stmt)
            await session.commit()
    except Exception:
        return


