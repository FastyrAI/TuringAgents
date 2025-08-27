"""Async audit storage helpers for message lifecycle tracking.

This module provides thin, best-effort wrappers around SQLAlchemy's async
engine to persist audit data into Supabase/PostgreSQL tables. Failures are
intentionally non-fatal to avoid impacting the hot-path of producers/workers.

Why this exists:
- Centralizes redaction and resilience policy for audit writes
- Keeps business logic free of storage concerns

Usage example:
    from libs.models import MessageEventRecord
    from libs.constants import EVENT_CREATED
    await record_message_event(MessageEventRecord(
        message_id="abc", org_id="demo", event_type=EVENT_CREATED,
        details={"source": "producer"},
    ))
"""
from __future__ import annotations

from typing import Any, TYPE_CHECKING
import logging

from sqlalchemy.dialects.postgresql import insert

from libs.config import ENVIRONMENT
from libs.db import get_session
from libs.orm_models import Message, MessageEvent, DLQMessage

if TYPE_CHECKING:  # pragma: no cover - import only for typing
    from libs.models import MessageEventRecord, DLQMessageRecord, MessageRecord


def _apply_redaction(obj: dict[str, Any]) -> dict[str, Any]:
    """Apply environment-specific redaction to payload fields.

    In production, sensitive fields like ``payload`` and ``details`` are
    replaced with a minimal redaction marker to avoid storing PII.

    Why: Compliance and least-privilege storage principles.

    Example:
        data = {"payload": {"ssn": "..."}, "details": {"ip": "1.2.3.4"}}
        safe = _apply_redaction(data)
    """
    if ENVIRONMENT == "production":
        redacted = dict(obj)
        if "payload" in redacted:
            redacted["payload"] = {"redacted": True}
        if "details" in redacted:
            redacted["details"] = {"redacted": True}
        return redacted
    return obj


def _log_dev_error(operation: str, exc: Exception) -> None:
    """Log storage errors verbosely in non-production environments.

    This exists to make CI/local failures visible, while keeping production
    paths silent to avoid noisy logs and potential PII leakage.

    Example:
        try:
            ...
        except Exception as e:
            _log_dev_error("insert message_event", e)
    """
    if ENVIRONMENT != "production":
        logging.getLogger(__name__).exception("audit storage error during %s", operation, exc_info=exc)


async def _insert_event(payload: dict[str, Any]) -> None:
    """Persist a single row into ``message_events``.

    Best-effort: any exception is swallowed in production, but logged in
    development/staging to aid debugging.

    Example:
        await _insert_event({"org_id": "demo", "event_type": "created"})
    """
    try:
        async with get_session() as session:
            table: Any = getattr(MessageEvent, "__table__")
            await session.execute(table.insert().values(**payload))
            await session.commit()
    except Exception as exc:  # noqa: BLE001
        _log_dev_error("insert message_event", exc)
        return


async def record_message_event(event: dict[str, Any] | "MessageEventRecord") -> None:
    """Insert a lifecycle event into ``message_events``.

    Accepts either a plain dict or a `MessageEventRecord` instance.
    Why: Provides a schemaed API for callers while preserving flexibility.

    Example:
        await record_message_event({
            "message_id": "abc", "org_id": "demo", "event_type": "created"
        })
    """
    """Write a message lifecycle event to Supabase (table: message_events)."""
    from libs.models import MessageEventRecord

    payload = event.model_dump() if isinstance(event, MessageEventRecord) else event
    # Apply standard redaction policy
    payload = _apply_redaction(payload)
    await _insert_event(payload)


async def record_dlq_message(entry: dict[str, Any] | "DLQMessageRecord") -> None:
    """Insert a DLQ row into ``dlq_messages``.

    Accepts either a plain dict or a `DLQMessageRecord` instance.
    Why: Capture terminal failures for later analysis and replay.

    Example:
        await record_dlq_message({
            "org_id": "demo", "original_message": {...}, "error": {"msg": "boom"}
        })
    """
    """Write a DLQ entry to Supabase (table: dlq_messages)."""
    from libs.models import DLQMessageRecord

    payload = entry.model_dump() if isinstance(entry, DLQMessageRecord) else entry
    if ENVIRONMENT == "production":
        payload = {**payload, "original_message": {"redacted": True}, "error": {"redacted": True}}
    try:
        async with get_session() as session:
            table: Any = getattr(DLQMessage, "__table__")
            await session.execute(table.insert().values(**payload))
            await session.commit()
    except Exception as exc:  # noqa: BLE001
        _log_dev_error("insert dlq_message", exc)
        return


async def upsert_message(record: dict[str, Any] | "MessageRecord") -> None:
    """Upsert a row into ``messages`` keyed by ``message_id``.

    Accepts either a plain dict or a `MessageRecord` instance.
    Why: Keep latest status/payload for quick lookups.

    Example:
        await upsert_message({
            "message_id": "abc", "org_id": "demo", "status": "QUEUED", "payload": {}
        })
    """
    """Upsert a message record in Supabase (table: messages)."""
    from libs.models import MessageRecord

    payload = record.model_dump() if isinstance(record, MessageRecord) else record
    # Apply standard redaction for message payloads
    payload = _apply_redaction(payload)
    try:
        async with get_session() as session:
            table: Any = getattr(Message, "__table__")
            stmt = insert(Message).values(**payload)
            do_update_stmt = stmt.on_conflict_do_update(
                index_elements=[table.c.message_id],
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
    except Exception as exc:  # noqa: BLE001
        _log_dev_error("upsert message", exc)
        return


