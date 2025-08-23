"""
Replay DLQ messages back into the org request exchange.

Usage:
  uv run python -m scripts.replay_dlq --org-id demo-org --limit 1 [--priority 1]
"""

import argparse
import asyncio
from typing import Any

import aio_pika

from libs.config import RABBITMQ_URL
from libs.rabbit import publish_request
from libs.audit import record_message_event

import os
from sqlalchemy import select


async def replay(org_id: str, limit: int, priority: int) -> None:
    from libs.db import get_session
    from libs.orm_models import DLQMessage
    messages = []
    async with get_session() as session:
        res = await session.execute(select(DLQMessage.original_message).where(DLQMessage.org_id == org_id).order_by(DLQMessage.dlq_timestamp.asc()).limit(limit))
        messages = [row[0] for row in res.all()]
    if not messages:
        print("No DLQ messages found")
        return

    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    async with connection:
        channel = await connection.channel()
        for msg in messages:
            # Reset retry_count on replay
            msg["retry_count"] = 0
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
    args = parser.parse_args()

    asyncio.run(replay(args.org_id, args.limit, args.priority))


if __name__ == "__main__":
    main()


