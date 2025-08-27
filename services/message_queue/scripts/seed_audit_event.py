"""Seed a minimal audit trail into Supabase/Postgres for e2e checks.

Writes a synthetic message row and two events: "created" and "enqueued".

Environment variables:
- ORG_ID: organization id (default: demo-org)
- MESSAGE_ID: optional pre-set message id; if omitted, a UUID is generated

Usage:
  uv run python -m scripts.seed_audit_event
"""

from __future__ import annotations

import asyncio
import os
import uuid
from typing import Any

from libs.audit_pipeline import audit_created_enqueued


async def _seed() -> dict[str, Any]:
    org_id = os.getenv("ORG_ID", "demo-org")
    message_id = os.getenv("MESSAGE_ID", str(uuid.uuid4()))
    message: dict[str, Any] = {
        "message_id": message_id,
        "version": "1.0.0",
        "org_id": org_id,
        "type": "agent_message",
        "priority": 2,
        "created_by": {"type": "system", "id": "seed"},
        "created_at": __import__('libs.validation', fromlist=['now_iso']).now_iso(),
        "goal_id": str(uuid.uuid4()),
        "task_id": str(uuid.uuid4()),
        "context": {"seed": True},
        "metadata": {},
    }
    await audit_created_enqueued(message, org_id)
    return {"message_id": message_id, "org_id": org_id}


def main() -> None:
    result = asyncio.run(_seed())
    print(result)


if __name__ == "__main__":
    main()


