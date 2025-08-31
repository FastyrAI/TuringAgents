"""Audit storage helpers with async batch writes to PostgreSQL via SQLAlchemy.

This module provides small, well-documented helpers for recording audit
artifacts to the database. Message lifecycle events are batched to reduce
write amplification and to keep hot paths fast and predictable.

Why this exists:
- Producers/workers emit many lifecycle events; single-row writes can become
  a bottleneck. Batching (N events or T milliseconds) improves throughput.
- Centralizing redaction and write patterns ensures consistent behavior.

How to use:
- Call ``await record_message_event({...})`` anywhere you need to record an
  event. The call is non-blocking and enqueues the event into an internal
  batcher that flushes automatically.
- Optionally call ``await flush_audit_events()`` before shutdown to flush
  any pending events.

Example:
    >>> await record_message_event({
    ...     "message_id": "m-123",
    ...     "org_id": "org-1",
    ...     "event_type": "processing",
    ...     "details": {"worker": "w1"},
    ... })
    >>> await flush_audit_events()  # during shutdown
"""
from __future__ import annotations

import asyncio
from typing import Any, TYPE_CHECKING, Optional
import logging

from sqlalchemy.dialects.postgresql import insert

from libs.config import ENVIRONMENT
from libs.db import get_session, is_database_configured
from libs.orm_models import Message, MessageEvent, DLQMessage
from libs.metrics import (
    AUDIT_EVENT_ENQUEUED_TOTAL,
    AUDIT_EVENTS_DROPPED_TOTAL,
    AUDIT_BATCH_FLUSH_TOTAL,
    AUDIT_BATCH_SIZE,
    AUDIT_EVENT_WRITE_SECONDS,
)
from libs.config import Settings

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


class AuditEventBatcher:
    """Async batching pipeline for message lifecycle events.

    Purpose:
        Collect audit events in-memory and flush them to the database in
        batches. This improves performance while keeping hot paths non-blocking.

    When to use:
        This class is used internally by ``record_message_event``. Most code
        should not instantiate it directly; use ``get_audit_batcher()``.

    Properties:
        - batch_size: maximum number of events per write
        - flush_interval_ms: periodic flush interval in milliseconds
        - queue_max: maximum buffered events before drops occur

    Methods:
        - start(): create the background task if not running
        - is_running: bool property
        - enqueue(event): add an event to the buffer quickly
        - flush(reason): flush pending events immediately with reason label
        - shutdown(): stop and flush remaining events

    Example:
        >>> batcher = AuditEventBatcher(100, 1000, 50000)
        >>> batcher.start()
        >>> await batcher.enqueue({"org_id": "o", "event_type": "created"})
        >>> await batcher.flush("manual")
        >>> await batcher.shutdown()
    """

    def __init__(self, batch_size: int, flush_interval_ms: int, queue_max: int) -> None:
        self._batch_size = max(1, int(batch_size))
        self._flush_interval_s = max(0.001, float(flush_interval_ms) / 1000.0)
        self._queue_max = max(self._batch_size, int(queue_max))
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=self._queue_max)
        self._stop_event = asyncio.Event()
        self._flush_now = asyncio.Event()
        self._task: Optional[asyncio.Task[None]] = None

    @property
    def is_running(self) -> bool:
        """Return True if the background flush task is active."""
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        """Start the background flusher if not already running.

        This is idempotent. Calling it multiple times is safe.
        """
        if not self.is_running:
            self._stop_event.clear()
            self._task = asyncio.create_task(self._run(), name="audit-batcher")

    async def enqueue(self, event: dict[str, Any]) -> None:
        """Enqueue an audit event quickly.

        The event is redacted (in production) before being buffered. If the
        buffer is full, the event is dropped and a metric increments. When the
        buffer reaches the batch size, a flush is triggered asynchronously.

        Example:
            >>> await batcher.enqueue({"org_id": "o", "event_type": "created"})
        """
        try:
            payload = _apply_redaction(event)
            AUDIT_EVENT_ENQUEUED_TOTAL.labels(event_type=str(payload.get("event_type", "unknown"))).inc()
            self._queue.put_nowait(payload)
        except asyncio.QueueFull:
            AUDIT_EVENTS_DROPPED_TOTAL.inc()
            return
        if self._queue.qsize() >= self._batch_size:
            # Signal immediate flush due to size threshold
            self._flush_now.set()

    async def _run(self) -> None:
        """Background loop that flushes by size or by interval.

        The loop waits for either the size-triggered event or the interval
        timeout. On wake, it drains up to batch_size events and writes them.
        """
        while not self._stop_event.is_set():
            try:
                try:
                    await asyncio.wait_for(self._flush_now.wait(), timeout=self._flush_interval_s)
                    reason = "size"
                except asyncio.TimeoutError:
                    reason = "interval"
                finally:
                    # Always clear the signal to allow future waits
                    self._flush_now.clear()

                await self._flush_once(reason)
            except Exception:
                # Swallow to keep the batcher alive; write failures are best-effort
                continue

    async def _flush_once(self, reason: str) -> None:
        """Drain up to a batch of events and write them, updating metrics."""
        items: list[dict[str, Any]] = []
        while len(items) < self._batch_size and not self._queue.empty():
            try:
                items.append(self._queue.get_nowait())
            except asyncio.QueueEmpty:
                break

        if not items:
            return

        AUDIT_BATCH_FLUSH_TOTAL.labels(reason=reason).inc()
        AUDIT_BATCH_SIZE.observe(len(items))
        start = asyncio.get_event_loop().time()
        await self._write_batch(items)
        elapsed = asyncio.get_event_loop().time() - start
        AUDIT_EVENT_WRITE_SECONDS.observe(elapsed)

    async def _write_batch(self, items: list[dict[str, Any]]) -> None:
        """Write a batch of events to the database in a single INSERT.

        In tests, this method can be monkeypatched to capture writes.
        """
        # Best-effort: if DB isn't configured, no-op and log a warning once per flush.
        if not is_database_configured():
            logging.getLogger(__name__).warning("audit flush skipped: database is not configured")
            return
        try:
            async with get_session() as session:
                table: Any = getattr(MessageEvent, "__table__")
                await session.execute(table.insert().values(items))
                await session.commit()
        except Exception as exc:  # noqa: BLE001
            _log_dev_error("batch insert message_events", exc)
            return

    async def flush(self, reason: str = "manual") -> None:
        """Flush any pending events immediately.

        Example:
            >>> await batcher.flush("shutdown")
        """
        await self._flush_once(reason)

    async def shutdown(self) -> None:
        """Stop the background loop and flush remaining events once.

        Example:
            >>> await batcher.shutdown()
        """
        if self.is_running and self._task is not None:
            self._stop_event.set()
            self._flush_now.set()
            # Give the task a moment to exit
            try:
                await asyncio.wait_for(self._task, timeout=self._flush_interval_s * 2)
            except Exception:
                pass
        # Final best-effort flush
        await self.flush("shutdown")


_batcher: Optional[AuditEventBatcher] = None


def get_audit_batcher() -> AuditEventBatcher:
    """Return a process-local audit batcher instance, creating it if needed.

    Reads configuration from ``Settings`` to size buffers and intervals.

    Example:
        >>> batcher = get_audit_batcher()
        >>> batcher.start()
    """
    global _batcher
    if _batcher is None:
        cfg = Settings()
        _batcher = AuditEventBatcher(
            batch_size=cfg.audit_batch_size,
            flush_interval_ms=cfg.audit_flush_interval_ms,
            queue_max=cfg.audit_queue_max,
        )
        _batcher.start()
    elif not _batcher.is_running:
        _batcher.start()
    return _batcher
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




async def record_message_event(event: dict[str, Any] | "MessageEventRecord") -> None:
    """Insert a lifecycle event into ``message_events``.

    Accepts either a plain dict or a `MessageEventRecord` instance.
    Why: Provides a schemaed API for callers while preserving flexibility.

    Example:
        await record_message_event({
            "message_id": "abc", "org_id": "demo", "event_type": "created"
        })
    """
    from libs.models import MessageEventRecord

    payload = event.model_dump() if isinstance(event, MessageEventRecord) else event
    # Apply standard redaction policy and enqueue to batcher
    payload = _apply_redaction(payload)
    await get_audit_batcher().enqueue(payload)


async def record_dlq_message(entry: dict[str, Any] | "DLQMessageRecord") -> None:
    """Insert a DLQ row into ``dlq_messages``.

    Accepts either a plain dict or a `DLQMessageRecord` instance.
    Why: Capture terminal failures for later analysis and replay.

    Example:
        await record_dlq_message({
            "org_id": "demo", "original_message": {...}, "error": {"msg": "boom"}
        })
    """
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


async def flush_audit_events() -> None:
    """Flush any buffered audit events immediately.

    This is useful during controlled shutdowns or before process exit.

    Example:
        >>> await flush_audit_events()
    """
    await get_audit_batcher().flush("manual")


async def shutdown_audit_batcher() -> None:
    """Shutdown the audit batcher and perform a final flush.

    Example:
        >>> await shutdown_audit_batcher()
    """
    await get_audit_batcher().shutdown()


