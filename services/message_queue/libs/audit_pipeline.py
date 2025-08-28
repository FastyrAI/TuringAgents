"""High-level audit pipeline helpers for common message lifecycle transitions.

These functions wrap the lower-level ``libs.audit`` helpers to perform the
appropriate upserts and event writes for common state changes (created,
dequeued, processing, completed, failed->retry, dead-lettered, etc.).

Usage example:
    >>> await audit_created_enqueued(message_dict, org_id)
    >>> await audit_dequeued_processing(payload, org_id, worker_id)
"""

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
    EVENT_PROMOTED,
    EVENT_CONFLICT_DETECTED,
    EVENT_CONFLICT_RESOLVED,
    EVENT_CONFLICT_RESOLUTION_FAILED,
)


async def audit_created_enqueued(message: dict[str, Any], org_id: str) -> None:
    """Record created+enqueued audit and upsert initial message state."""
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
    """Record dequeued+processing audit and upsert processing state."""
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
    """Record completed audit and upsert final state to COMPLETED."""
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


async def audit_failed_then_retry(payload: dict[str, Any], org_id: str, error: Exception, next_retry_count: int, delay_ms: int) -> None:
    """Record failure audit, upsert FAILED/RETRYING, and record retry schedule."""
    await record_message_event(
        MessageEventRecord(
            message_id=payload.get("message_id"),
            org_id=org_id,
            event_type=EVENT_FAILED,
            details={"error": str(error)},
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
            details={"delay_ms": delay_ms, "retry_count": next_retry_count},
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
    """Record dead-letter audit, write DLQ row, and upsert DEAD_LETTERED."""
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


async def audit_promoted(message_id: str, org_id: str, from_priority: int, to_priority: int) -> None:
    """Record that a message priority was promoted (e.g., P3->P2).

    Why: The ADR requires explicit auditability of time-based promotions.
    Example:
        >>> await audit_promoted("m1", "org", 3, 2)
    """
    await record_message_event(
        MessageEventRecord(
            message_id=message_id,
            org_id=org_id,
            event_type=EVENT_PROMOTED,
            details={"from": int(from_priority), "to": int(to_priority)},
        )
    )


async def audit_conflict_detected(message_id: str | None, org_id: str, resource: str, reason: str) -> None:
    """Record that a potential processing conflict was detected.

    Example:
        >>> await audit_conflict_detected("m1", "org", "doc:42", "write-write")
    """
    await record_message_event(
        MessageEventRecord(
            message_id=message_id,
            org_id=org_id,
            event_type=EVENT_CONFLICT_DETECTED,
            details={"resource": resource, "reason": reason},
        )
    )


async def audit_conflict_resolved(message_id: str | None, org_id: str, resolution: str) -> None:
    """Record that a conflict was automatically resolved.

    Example:
        >>> await audit_conflict_resolved("m1", "org", "deferred other task")
    """
    await record_message_event(
        MessageEventRecord(
            message_id=message_id,
            org_id=org_id,
            event_type=EVENT_CONFLICT_RESOLVED,
            details={"resolution": resolution},
        )
    )


async def audit_conflict_resolution_failed(message_id: str | None, org_id: str, error: str) -> None:
    """Record that conflict resolution failed (needs human escalation).

    Example:
        >>> await audit_conflict_resolution_failed("m1", "org", "ambiguous ownership")
    """
    await record_message_event(
        MessageEventRecord(
            message_id=message_id,
            org_id=org_id,
            event_type=EVENT_CONFLICT_RESOLUTION_FAILED,
            details={"error": error},
        )
    )

