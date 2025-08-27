"""Async load generator to publish N messages at M concurrency.

Prints aggregate throughput and approximate publish latency.

Example:
  ORG_ID=demo-org COUNT=200 CONCURRENCY=20 PRIORITY=2 uv run python -m scripts.load_test
"""

import asyncio
import os
import time
import uuid
from statistics import mean

import aio_pika

from libs.config import RABBITMQ_URL, parse_priority
from libs.rabbit import publish_request, declare_org_topology, connect
from libs.validation import validate_message, now_iso


from aio_pika.abc import AbstractChannel


async def publish_one(channel: AbstractChannel, org_id: str, priority: int) -> float:
    start = time.perf_counter()
    msg: dict[str, object] = {
        "message_id": str(uuid.uuid4()),
        "version": "1.0.0",
        "org_id": org_id,
        "type": "agent_message",
        "priority": priority,
        "created_by": {"type": "system", "id": "load"},
        "created_at": now_iso(),
    }
    validate_message(msg)
    await publish_request(channel, org_id, msg, logical_priority=priority)
    return time.perf_counter() - start


async def main() -> None:
    org_id = os.getenv("ORG_ID", "demo-org")
    count = int(os.getenv("COUNT", "100"))
    concurrency = int(os.getenv("CONCURRENCY", "10"))
    priority = parse_priority(os.getenv("PRIORITY", "2"))

    connection = await connect(RABBITMQ_URL)
    async with connection:
        channel = await connection.channel()
        await declare_org_topology(channel, org_id)

        sem = asyncio.Semaphore(concurrency)
        timings = []

        async def worker():
            async with sem:
                t = await publish_one(channel, org_id, priority)
                timings.append(t)

        started = time.perf_counter()
        await asyncio.gather(*(worker() for _ in range(count)))
        total = time.perf_counter() - started

        print(f"published={count} concurrency={concurrency} total_sec={total:.2f} tps={count/total:.1f}")
        if timings:
            print(f"publish_latency_ms: p50~{1000*mean(timings):.2f}")


if __name__ == "__main__":
    asyncio.run(main())


