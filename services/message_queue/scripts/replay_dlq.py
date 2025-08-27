"""
Replay DLQ messages back into the org request exchange.

Usage:
  uv run python -m scripts.replay_dlq --org-id demo-org --limit 1 [--priority 1]
"""

import argparse
import asyncio
from typing import Any

from libs.config import RABBITMQ_URL
from libs.rabbit import publish_request, connect
from libs.audit import record_message_event

import os
from sqlalchemy import select


async def replay(org_id: str, limit: int, priority: int, *, dry_run: bool, msg_type: str | None, since: str | None, until: str | None, yes: bool) -> None:
    from libs.db import get_session
    from libs.orm_models import DLQMessage
    messages = []
    async with get_session() as session:
        query = select(DLQMessage.id, DLQMessage.original_message, DLQMessage.dlq_timestamp).where(DLQMessage.org_id == org_id)
        if msg_type:
            # Filter by message type inside JSONB document
            query = query.where(DLQMessage.original_message["type"].as_string() == msg_type)
        if since:
            from datetime import datetime
            query = query.where(DLQMessage.dlq_timestamp >= datetime.fromisoformat(since))
        if until:
            from datetime import datetime
            query = query.where(DLQMessage.dlq_timestamp <= datetime.fromisoformat(until))
        query = query.order_by(DLQMessage.dlq_timestamp.asc()).limit(limit)
        res = await session.execute(query)
        rows = res.all()
        messages = rows
    if not messages:
        print("No DLQ messages found")
        return

    # Priority override confirmation
    if priority is not None:
        # Check if any message has a different priority
        diffs = [row[1].get("priority") for row in messages if int(row[1].get("priority", 2)) != int(priority)]
        if diffs and not yes:
            print("Refusing to replay with overridden priority without --yes confirmation.")
            print(f"{len(diffs)} messages have a different original priority.")
            return

    if dry_run:
        print(f"Dry-run: would replay {len(messages)} messages for org={org_id} priority=P{priority}")
        return

    connection = await connect(RABBITMQ_URL)
    async with connection:
        channel = await connection.channel()
        for row in messages:
            _dlq_id, msg, ts = row
            # Reset retry_count on replay
            msg["retry_count"] = 0
            # Annotate replay origin
            ctx = msg.get("context") or {}
            ctx["replayed_from"] = {"dlq": True}
            msg["context"] = ctx
            await publish_request(channel, org_id, msg, logical_priority=priority)
            await record_message_event({
                "message_id": msg.get("message_id"),
                "org_id": org_id,
                "event_type": "replayed",
                "details": {"source": "dlq_replay"},
            })
            print(f"Replayed {msg.get('message_id')}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay DLQ messages")
    parser.add_argument("--org-id", required=True)
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--priority", type=int, default=2)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--type", dest="msg_type", help="Filter by message type")
    parser.add_argument("--since", help="ISO timestamp lower bound (inclusive)")
    parser.add_argument("--until", help="ISO timestamp upper bound (inclusive)")
    parser.add_argument("--yes", action="store_true", help="Auto-confirm priority override")
    args = parser.parse_args()

    asyncio.run(replay(args.org_id, args.limit, args.priority, dry_run=args.dry_run, msg_type=args.msg_type, since=args.since, until=args.until, yes=args.yes))


if __name__ == "__main__":
    main()


