from __future__ import annotations

from typing import Any

from libs.audit import record_message_event, upsert_message, record_dlq_message
from libs.models import MessageRecord, MessageEventRecord, DLQMessageRecord
from libs.constants import (
    STATUS_QUEUED,
    STATUS_PROCESSING,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_RETRYING,
    STATUS_DEAD_LETTERED,
    EVENT_CREATED,
    EVENT_ENQUEUED,
    EVENT_DEQUEUED,
    EVENT_PROCESSING,
    EVENT_COMPLETED,
    EVENT_FAILED,
    EVENT_RETRY_SCHEDULED,
    EVENT_DEAD_LETTER,
)


async def audit_created_enqueued(message: dict[str, Any], org_id: str) -> None:
    await upsert_message(
        MessageRecord(
            message_id=message["message_id"],
            org_id=org_id,
            agent_id=message.get("agent_id"),
            type=message["type"],
            priority=message.get("priority", 2),
            status=STATUS_QUEUED,
            payload=message,
        )
    )
    await record_message_event(
        MessageEventRecord(
            message_id=message["message_id"],
            org_id=org_id,
            event_type=EVENT_CREATED,
            details={"source": "producer"},
        )
    )
    await record_message_event(
        MessageEventRecord(
            message_id=message["message_id"],
            org_id=org_id,
            event_type=EVENT_ENQUEUED,
            details={"exchange": f"org.{org_id}.requests"},
        )
    )


async def audit_dequeued_processing(payload: dict[str, Any], org_id: str, worker_id: str) -> None:
    await record_message_event(
        MessageEventRecord(
            message_id=payload.get("message_id"),
            org_id=org_id,
            event_type=EVENT_DEQUEUED,
            details={"queue": f"org.{org_id}.requests.q"},
        )
    )
    await record_message_event(
        MessageEventRecord(
            message_id=payload.get("message_id"),
            org_id=org_id,
            event_type=EVENT_PROCESSING,
            details={"worker": worker_id},
        )
    )
    await upsert_message(
        MessageRecord(
            message_id=payload.get("message_id"),
            org_id=org_id,
            agent_id=payload.get("agent_id"),
            type=payload.get("type"),
            priority=payload.get("priority"),
            status=STATUS_PROCESSING,
            payload=payload,
        )
    )


async def audit_completed(payload: dict[str, Any], org_id: str, worker_id: str) -> None:
    await record_message_event(
        MessageEventRecord(
            message_id=payload.get("message_id"),
            org_id=org_id,
            event_type=EVENT_COMPLETED,
            details={"worker": worker_id},
        )
    )
    await upsert_message(
        MessageRecord(
            message_id=payload.get("message_id"),
            org_id=org_id,
            agent_id=payload.get("agent_id"),
            type=payload.get("type"),
            priority=payload.get("priority"),
            status=STATUS_COMPLETED,
            payload=payload,
        )
    )


async def audit_failed_then_retry(
    payload: dict[str, Any],
    org_id: str,
    error: Exception,
    next_retry_count: int,
    delay_ms: int,
    *,
    demotion_from: int | None = None,
    demotion_to: int | None = None,
    strategy: str | None = None,
    error_type: str | None = None,
) -> None:
    """Audit failed -> scheduled retry transition with rich context.

    Why
    ----
    Provides observability for failures and subsequent retry scheduling,
    including priority demotions and policy strategy, as per ADR Step 1.2.

    How to use
    -----------
    Call after a handler raises, and a retry has been decided. Pass the updated
    payload (with incremented ``retry_count`` and possibly demoted ``priority``),
    and include optional demotion/policy fields for richer analytics.

    Examples
    --------
    >>> await audit_failed_then_retry(payload, "org", Exception("x"), 1, 1000, demotion_from=1, demotion_to=2, strategy="exponential", error_type="Exception")
    """
    await record_message_event(
        MessageEventRecord(
            message_id=payload.get("message_id"),
            org_id=org_id,
            event_type=EVENT_FAILED,
            details={
                "error": str(error),
                **({"error_type": error_type} if error_type else {}),
            },
        )
    )
    await upsert_message(
        MessageRecord(
            message_id=payload.get("message_id"),
            org_id=org_id,
            agent_id=payload.get("agent_id"),
            type=payload.get("type"),
            priority=payload.get("priority"),
            status=STATUS_FAILED,
            payload=payload,
        )
    )
    await record_message_event(
        MessageEventRecord(
            message_id=payload.get("message_id"),
            org_id=org_id,
            event_type=EVENT_RETRY_SCHEDULED,
            details={
                "delay_ms": delay_ms,
                "retry_count": next_retry_count,
                **({"demotion_from": demotion_from} if demotion_from is not None else {}),
                **({"demotion_to": demotion_to} if demotion_to is not None else {}),
                **({"strategy": strategy} if strategy else {}),
                **({"error_type": error_type} if error_type else {}),
            },
        )
    )
    await upsert_message(
        MessageRecord(
            message_id=payload.get("message_id"),
            org_id=org_id,
            agent_id=payload.get("agent_id"),
            type=payload.get("type"),
            priority=payload.get("priority"),
            status=STATUS_RETRYING,
            payload=payload,
        )
    )


async def audit_dead_letter(payload: dict[str, Any], org_id: str, error: Exception) -> None:
    await record_message_event(
        MessageEventRecord(
            message_id=payload.get("message_id"),
            org_id=org_id,
            event_type=EVENT_DEAD_LETTER,
            details={"error": str(error)},
        )
    )
    await record_dlq_message(
        DLQMessageRecord(
            org_id=org_id,
            original_message=payload,
            error={"type": error.__class__.__name__, "message": str(error)},
            can_replay=True,
        )
    )
    await upsert_message(
        MessageRecord(
            message_id=payload.get("message_id"),
            org_id=org_id,
            agent_id=payload.get("agent_id"),
            type=payload.get("type"),
            priority=payload.get("priority"),
            status=STATUS_DEAD_LETTERED,
            payload=payload,
        )
    )


