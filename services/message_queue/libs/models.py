"""Pydantic record models used for audit storage.

These models validate the shapes we write to Supabase tables and make the
call sites more explicit than passing generic dicts around.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class MessageRecord(BaseModel):
    """Row for the `messages` table capturing the latest message state."""
    model_config = ConfigDict(extra="allow")

    message_id: Optional[str]
    org_id: str
    agent_id: Optional[str] = None
    type: Optional[str] = None
    priority: Optional[int] = None
    status: str
    payload: dict[str, Any]


class MessageEventRecord(BaseModel):
    """Row for the `message_events` table capturing lifecycle events."""
    model_config = ConfigDict(extra="allow")

    message_id: Optional[str] = None
    org_id: str
    event_type: str
    details: Optional[dict[str, Any]] = None


class DLQMessageRecord(BaseModel):
    """Row for the `dlq_messages` table for terminal failures."""
    model_config = ConfigDict(extra="allow")

    org_id: str
    original_message: dict[str, Any]
    error: dict[str, Any]
    can_replay: bool = True


