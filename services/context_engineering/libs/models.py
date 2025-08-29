from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


ScopeName = Literal["session", "goal", "global"]


class Message(BaseModel):
    """Graph Message node representation.

    Includes session/goal scope and metadata for provenance.
    """

    model_config = ConfigDict(extra="allow")

    id: str = Field(default_factory=lambda: uuid4().hex)
    org_id: Optional[str] = None
    session_id: str
    goal_id: Optional[str] = None
    scope: ScopeName = "session"
    text: str
    ts: float = Field(default_factory=lambda: datetime.utcnow().timestamp())
    metadata: Dict[str, Any] | None = None


class Entity(BaseModel):
    """Graph Entity node representation."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(default_factory=lambda: uuid4().hex)
    name: str
    type: Optional[str] = None
    metadata: Dict[str, Any] | None = None


class Fact(BaseModel):
    """Symbolic fact triple extracted from messages or documents."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(default_factory=lambda: uuid4().hex)
    subject: str
    predicate: str
    object: str
    confidence: float = 1.0
    source_node_id: Optional[str] = None
    scope: ScopeName = "session"
    ts: float = Field(default_factory=lambda: datetime.utcnow().timestamp())


class Summary(BaseModel):
    """Graph Summary node representation."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(default_factory=lambda: uuid4().hex)
    org_id: Optional[str] = None
    session_id: str
    goal_id: Optional[str] = None
    text: str
    scope: ScopeName = "session"
    citations: List[str] = Field(default_factory=list)
    created_by: str = "router"
    ts: float = Field(default_factory=lambda: datetime.utcnow().timestamp())


class RetrievedItem(BaseModel):
    id: str
    text: str
    score: float
    source: str = "hybrid"


class AuditEvent(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    event_type: str
    payload: Dict[str, Any]
    ts: float = Field(default_factory=lambda: datetime.utcnow().timestamp())
