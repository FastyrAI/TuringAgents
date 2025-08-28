"""SQLAlchemy ORM models for message, audit events, DLQ, and support tables.

These declarative models mirror the Supabase/PostgreSQL schema used by the
message queue service. They are intentionally minimal and typed to make
queries readable and safe.

When to use:
- Use these models for database reads/writes anywhere in the service
  (workers, scripts, audit helpers).

Models provided:
- ``Message``: Latest state snapshot of each message
- ``MessageEvent``: Append-only lifecycle events for auditing
- ``DLQMessage``: Terminal failures captured for replay/analysis
- ``IdempotencyKey``: Uniqueness guard for deduplication
- ``PoisonCounter``: Rolling failure counters to detect poison messages
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all ORM models."""


class Message(Base):
    """Latest state snapshot of each message.

    Purpose:
        Store the most recent status and payload for quick lookups.

    Fields:
        - id: Surrogate primary key
        - message_id: Public identifier (unique)
        - org_id: Organization ID
        - agent_id: Target agent ID (optional)
        - type: Message type (optional)
        - priority: Logical priority (optional)
        - status: Current status string
        - payload: Latest message payload as JSONB
        - created_at: Creation timestamp
        - updated_at: Last update timestamp
    """
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    message_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    org_id: Mapped[str] = mapped_column(String, index=True)
    agent_id: Mapped[str | None] = mapped_column(String, nullable=True)
    type: Mapped[str | None] = mapped_column(String, nullable=True)
    priority: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String)
    payload: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class MessageEvent(Base):
    """Append-only lifecycle events emitted during message processing.

    Fields:
        - id: Surrogate primary key
        - message_id: Optional message identifier (may be null for aggregate events)
        - org_id: Organization ID
        - event_type: Event name (e.g., created, enqueued, completed)
        - details: Optional JSONB with additional context
        - created_at: Event timestamp
    """
    __tablename__ = "message_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    message_id: Mapped[str | None] = mapped_column(String, index=True)
    org_id: Mapped[str] = mapped_column(String, index=True)
    event_type: Mapped[str] = mapped_column(String)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class DLQMessage(Base):
    """Terminal failures stored for later analysis and replay.

    Fields:
        - id: Surrogate primary key
        - org_id: Organization ID
        - original_message: Original message payload as JSONB
        - error: Error details as JSONB
        - can_replay: Whether replay is permitted
        - dlq_timestamp: Time of DLQ insertion
    """
    __tablename__ = "dlq_messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = mapped_column(String, index=True)
    original_message: Mapped[dict] = mapped_column(JSONB)
    error: Mapped[dict] = mapped_column(JSONB)
    can_replay: Mapped[bool] = mapped_column(Boolean, default=True)
    dlq_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class IdempotencyKey(Base):
    """Uniqueness guard for deduplication.

    Uses a composite primary key of ``(org_id, dedup_key)``. Presence of a row
    indicates the key has been seen before.
    """
    __tablename__ = "idempotency_keys"
    org_id: Mapped[str] = mapped_column(String, primary_key=True)
    dedup_key: Mapped[str] = mapped_column(String, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class PoisonCounter(Base):
    """Rolling failure counter per ``(org_id, dedup_key)``.

    Used to detect poison messages and trigger quarantine when the counter
    exceeds a configured threshold.
    """
    __tablename__ = "poison_counters"
    org_id: Mapped[str] = mapped_column(String, primary_key=True)
    dedup_key: Mapped[str] = mapped_column(String, primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


