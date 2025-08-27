"""
Simple producer script.

- Validates a request message with Pydantic
- Emits audit records for created/enqueued
- Publishes to the per-org request exchange with AMQP priority
"""

import asyncio
import os
import uuid
from typing import Any

from libs.config import Settings, parse_priority
from libs.rabbit import publish_request, declare_org_topology, connect
from libs.rate_limit import get_rate_limiter
from libs.validation import validate_message, now_iso
from libs.audit_pipeline import audit_created_enqueued
from libs.backpressure import get_queue_depth, decide_throttle
from libs.tracing import start_tracing, get_tracer, inject_headers


async def main() -> None:
    """Build a demo message, audit it, and publish to the org queue."""
    # Tracing
    start_tracing("ta-producer")
    tracer = get_tracer("ta-producer")
    org_id = os.getenv("ORG_ID", "demo-org")
    priority = parse_priority(os.getenv("PRIORITY", "2"))
    msg_type = os.getenv("TYPE", "agent_message")
    force_error = os.getenv("FORCE_ERROR", "false").lower() in {"1", "true", "yes"}

    message: dict[str, Any] = {
        "message_id": str(uuid.uuid4()),
        "version": "1.0.0",
        "org_id": org_id,
        "type": msg_type,
        "priority": priority,
        "created_by": {"type": "system", "id": "producer"},
        "created_at": now_iso(),
        "goal_id": os.getenv("GOAL_ID", str(uuid.uuid4())),
        "task_id": os.getenv("TASK_ID", str(uuid.uuid4())),
        "context": {"demo": True, "force_error": force_error},
        "metadata": {},
    }

    # Raise on invalid schema/types
    validate_message(message)

    settings = Settings()
    limiter = get_rate_limiter(settings)
    # Rate limit before connecting to reduce connection churn under heavy load
    if limiter is not None and settings.rate_limit_enabled:
        await limiter.acquire(org_id=org_id, user_id="producer")
    connection = await connect(settings.rabbitmq_url)
    async with connection:
        # For P1–P3 enable publisher confirms; P0 remains fire-and-forget
        channel = await connection.channel(publisher_confirms=(priority != 0))
        await declare_org_topology(channel, org_id)

        # Backpressure-aware throttle (client-side):
        # - light: throttle P3 only
        # - heavy: throttle P2 and P3
        # - emergency: allow only P0
        depth = get_queue_depth(org_id)
        mode = decide_throttle(depth, __import__('libs.backpressure', fromlist=['BackpressureConfig']).BackpressureConfig())
        if (
            (mode == "light" and priority == 3)
            or (mode == "heavy" and priority >= 2)
            or (mode == "emergency" and priority != 0)
        ):
            print(f"throttled: mode={mode} priority=P{priority} depth={depth}")
            return

        # Audit (created + enqueued) prior to actual publish
        await audit_created_enqueued(message, org_id)

        # Publish to per-org priority queue with trace headers
        with tracer.start_as_current_span("publish") as span:
            span.set_attribute("message_id", message["message_id"])
            span.set_attribute("org_id", org_id)
            headers = inject_headers({"message_id": str(message["message_id"])})
            try:
                await publish_request(channel, org_id, message, logical_priority=priority, headers=headers)
                from libs.metrics import PUBLISH_ATTEMPT_TOTAL
                PUBLISH_ATTEMPT_TOTAL.labels(priority=f"P{priority}", result="ok").inc()
            except Exception as e:
                from libs.metrics import PUBLISH_ATTEMPT_TOTAL, PUBLISH_FAILED_TOTAL
                PUBLISH_ATTEMPT_TOTAL.labels(priority=f"P{priority}", result="error").inc()
                PUBLISH_FAILED_TOTAL.labels(reason=e.__class__.__name__).inc()
                span.record_exception(e)
                span.set_attribute("error", True)
                raise


if __name__ == "__main__":
    asyncio.run(main())


