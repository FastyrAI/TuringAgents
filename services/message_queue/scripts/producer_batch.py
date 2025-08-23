"""
Batch producer: publishes N messages in batches of size B.

Example:
  ORG_ID=demo-org COUNT=1000 BATCH_SIZE=100 PRIORITY=2 uv run python -m scripts.producer_batch
"""

import asyncio
import os
import uuid
from typing import Any

import aio_pika

from libs.config import Settings, parse_priority
from libs.rabbit import publish_requests_batch, declare_org_topology
from libs.validation import validate_message, now_iso
from libs.tracing import start_tracing, get_tracer, inject_headers


async def main() -> None:
    start_tracing("ta-producer-batch")
    tracer = get_tracer("ta-producer-batch")

    org_id = os.getenv("ORG_ID", "demo-org")
    count = int(os.getenv("COUNT", "100"))
    batch_size = int(os.getenv("BATCH_SIZE", "50"))
    priority = parse_priority(os.getenv("PRIORITY", "2"))

    settings = Settings()
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    async with connection:
        channel = await connection.channel(publisher_confirms=(priority != 0))
        await declare_org_topology(channel, org_id)

        items = []
        for _ in range(count):
            message: dict[str, Any] = {
                "message_id": str(uuid.uuid4()),
                "version": "1.0.0",
                "org_id": org_id,
                "type": "agent_message",
                "priority": priority,
                "created_by": {"type": "system", "id": "batch-producer"},
                "created_at": now_iso(),
            }
            validate_message(message)
            headers = inject_headers({"message_id": message["message_id"]})
            items.append({"message": message, "priority": priority, "headers": headers})

            if len(items) >= batch_size:
                with tracer.start_as_current_span("batch_publish"):
                    await publish_requests_batch(channel, org_id, items)
                items = []

        if items:
            with tracer.start_as_current_span("batch_publish"):
                await publish_requests_batch(channel, org_id, items)


if __name__ == "__main__":
    asyncio.run(main())


