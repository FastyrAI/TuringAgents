"""Pydantic-based validation for incoming request messages.

We use the `RequestMessage` model as the Python representation, while still
supporting JSON Schema export for cross-language consumers.
"""
from __future__ import annotations

import datetime as _dt
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, conint, constr


# -------------------------
# Pydantic models (v2)
# -------------------------

CreatedByType = Literal["user", "agent", "system"]
RequestMessageType = Literal[
    "model_call",
    "tool_call",
    "agent_message",
    "memory_save",
    "memory_retrieve",
    "memory_update",
    "agent_spawn",
    "agent_terminate",
]


class CreatedBy(BaseModel):
    """Identity of the actor that created the message."""
    model_config = ConfigDict(extra="forbid")
    type: CreatedByType
    id: str


class RequestMessage(BaseModel):
    """Canonical Python model for request messages placed on the queue."""
    # Allow extra fields for forward-compatibility
    model_config = ConfigDict(extra="allow")

    message_id: str
    version: constr(pattern=r"^\d+\.\d+\.\d+$")  # type: ignore[type-arg]
    org_id: str
    agent_id: Optional[str] = None
    type: RequestMessageType
    priority: conint(ge=0, le=3)  # type: ignore[type-arg]
    goal_id: Optional[str] = None
    task_id: Optional[str] = None
    parent_message_id: Optional[str] = None
    created_by: CreatedBy
    created_at: _dt.datetime
    retry_count: Optional[int] = Field(default=0, ge=0)
    max_retries: Optional[int] = Field(default=0, ge=0)
    context: Optional[dict[str, Any]] = None
    metadata: Optional[dict[str, Any]] = None


def validate_message(message: dict[str, Any]) -> None:
    """Validate a request message using Pydantic.

    Raises a `pydantic.ValidationError` if invalid.
    """
    # Instantiation performs validation; we discard the object since callers only need validation side-effect
    RequestMessage.model_validate(message)


def export_request_json_schema() -> dict[str, Any]:
    """Return the JSON Schema for `RequestMessage` (for cross-language validation)."""
    return RequestMessage.model_json_schema()


def now_iso() -> str:
    return _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


