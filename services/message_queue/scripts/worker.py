"""
Asynchronous org-scoped worker.

- Consumes a single per-organization request queue (priority queue)
- Processes messages and emits responses to per-agent response queues
- Handles retries via per-org delay queues and ships terminal failures to DLQ
- Emits lifecycle audit events and upserts message state into Supabase
"""

import asyncio
import json
import os
import signal
import time
from typing import Any, Callable, Dict, Awaitable

from aio_pika.abc import AbstractIncomingMessage

from libs.config import Settings
from libs.rabbit import (
    declare_org_topology,
    publish_response,
    declare_agent_response_topology,
    schedule_retry,
    publish_to_dlq,
    connect,
)
from libs.audit_pipeline import (
    audit_dequeued_processing,
    audit_completed,
    audit_failed_then_retry,
    audit_dead_letter,
)
from libs.retry import decide_retry
from libs.constants import DEFAULT_RETRY_DELAYS_MS
from libs.metrics import (
    start_metrics_server,
    WORKER_MESSAGE_TOTAL,
    WORKER_PROCESS_LATENCY_SECONDS,
    WORKER_RETRY_TOTAL,
    WORKER_DLQ_TOTAL,
    QUEUE_DEPTH,
    RETRY_DEMOTION_TOTAL,
    RETRY_POLICY_TOTAL,
)
from libs.backpressure import get_queue_depth
from libs.dedup import compute_dedup_key, mark_and_check
from libs.constants import EVENT_DUPLICATE_SKIPPED, STATUS_DUPLICATE
from libs.tracing import start_tracing, get_tracer, extract_context_from_headers
from opentelemetry import context  # type: ignore
from libs.poison import increment_failure, should_quarantine
from libs.audit import record_message_event, upsert_message  # type: ignore


Handler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class Worker:
    """Message worker bound to an org and emitting responses for a given agent."""

    def __init__(self, org_id: str, agent_id: str):
        self.org_id = org_id
        self.agent_id = agent_id
        self._stopping = asyncio.Event()
        # Exponential backoff delays; can be configured per deployment
        self.retry_delays = DEFAULT_RETRY_DELAYS_MS
        self.handlers: Dict[str, Callable[[dict[str, Any]], Any]] = {
            "agent_message": self.handle_agent_message,
            "model_call": self.handle_passthrough,
            "tool_call": self.handle_passthrough,
            "memory_save": self.handle_passthrough,
            "memory_retrieve": self.handle_passthrough,
            "memory_update": self.handle_passthrough,
            "agent_spawn": self.handle_passthrough,
            "agent_terminate": self.handle_passthrough,
        }

    async def run(self) -> None:
        """Connect to RabbitMQ and begin consuming the org queue."""
        # Start Prometheus metrics server (if not already started in this process)
        settings = Settings()
        port = settings.metrics_port
        try:
            start_metrics_server(port)
            print(f"Metrics server listening on :{port} /metrics")
        except OSError:
            # Already started in this process; ignore
            pass

        # Background task to sample queue depth periodically for visibility
        asyncio.create_task(self._sample_queue_depth())

        # Tracing
        start_tracing("ta-worker")
        self._tracer = get_tracer("ta-worker")

        connection = await connect(settings.rabbitmq_url)
        async with connection:
            channel = await connection.channel()
            # Apply QoS/prefetch from Settings
            try:
                await channel.set_qos(prefetch_count=settings.prefetch_count)
            except Exception:
                pass
            # Declare org request/DLQ topology and ensure agent response queues exist
            await declare_org_topology(channel, self.org_id)
            await declare_agent_response_topology(channel, self.agent_id)

            queue = await channel.get_queue(f"org.{self.org_id}.requests.q")
            print(f"Worker consuming org queue: org.{self.org_id}.requests.q -> agent {self.agent_id}")
            await queue.consume(self._on_message, no_ack=False)

            # Wait until stop() is called (SIGINT/SIGTERM)
            await self._stopping.wait()

    async def _sample_queue_depth(self) -> None:
        """Periodically poll queue depth and update a Gauge metric."""
        while not self._stopping.is_set():
            depth = get_queue_depth(self.org_id)
            QUEUE_DEPTH.labels(org_id=self.org_id).set(depth)
            await asyncio.sleep(2)

    async def _on_message(self, message: AbstractIncomingMessage) -> None:
        """Core processing lifecycle for a single message."""
        start_ts = time.perf_counter()
        async with message.process(requeue=False):
            try:
                payload = json.loads(message.body)
                msg_type = payload.get("type")
                print(f"Worker received message {payload.get('message_id')} type={msg_type}")

                # Audit the transition to dequeued/processing and mark status
                await audit_dequeued_processing(payload, self.org_id, self.agent_id)

                # Idempotency check: skip duplicates
                dedup_key = compute_dedup_key(payload)
                if not await mark_and_check(self.org_id, dedup_key):
                    await record_message_event({
                        "message_id": payload.get("message_id"),
                        "org_id": self.org_id,
                        "event_type": EVENT_DUPLICATE_SKIPPED,
                        "details": {"dedup_key": dedup_key},
                    })
                    await upsert_message({
                        "message_id": payload.get("message_id"),
                        "org_id": self.org_id,
                        "agent_id": payload.get("agent_id"),
                        "type": payload.get("type"),
                        "priority": payload.get("priority"),
                        "status": STATUS_DUPLICATE,
                        "payload": payload,
                    })
                    WORKER_MESSAGE_TOTAL.labels(status="duplicate", type=msg_type).inc()
                    return

                # Route to the handler registry. Keep business logic in handlers.
                # For testing retry/DLQ path, a producer can set context.force_error = True
                handler = self.handlers.get(msg_type, self.handle_unknown)
                if payload.get("context", {}).get("force_error"):
                    raise RuntimeError("Forced error for retry testing")

                # Use incoming trace context from headers to continue the trace
                ctx = extract_context_from_headers(message.headers)
                token = context.attach(ctx)
                try:
                    with self._tracer.start_as_current_span("process") as span:
                        span.set_attribute("message_id", payload.get("message_id"))
                        span.set_attribute("org_id", self.org_id)
                        result = await handler(payload)
                    await self._emit_result(payload, result)
                    await audit_completed(payload, self.org_id, self.agent_id)
                finally:
                    context.detach(token)

                WORKER_MESSAGE_TOTAL.labels(status="success", type=msg_type).inc()
            except Exception as exc:  # noqa: BLE001
                # Failure path: record failure first, then retry or dead-letter
                print(f"Worker error: {exc}")
                p: dict[str, Any]
                try:
                    p = json.loads(message.body)
                except Exception:
                    p = {"org_id": self.org_id}

                # Compute retry decision with policy + demotion per ADR Step 1.2
                org = p.get("org_id", self.org_id)
                old_priority = int(p.get("priority", 2))
                decision = decide_retry(p, exc, delays=self.retry_delays)

                # Poison pill detection: if repeated failures exceed threshold, quarantine
                dedup_key = compute_dedup_key(p)
                fail_count = await increment_failure(org, dedup_key)
                if await should_quarantine(org, dedup_key):
                    await record_message_event({
                        "message_id": p.get("message_id"),
                        "org_id": org,
                        "event_type": "poison_quarantined",
                        "details": {"dedup_key": dedup_key, "fail_count": fail_count},
                    })
                    await upsert_message({
                        "message_id": p.get("message_id"),
                        "org_id": org,
                        "agent_id": p.get("agent_id"),
                        "type": p.get("type"),
                        "priority": p.get("priority"),
                        "status": "QUARANTINED",
                        "payload": p,
                    })
                    from libs.metrics import POISON_QUARANTINED_TOTAL
                    POISON_QUARANTINED_TOTAL.labels(type=p.get("type")).inc()
                    return

                if decision.should_retry:
                    # Apply demotion and increment retry_count
                    p["priority"] = decision.next_priority
                    p["retry_count"] = decision.next_retry_count
                    # Publish to delay queue so it DLXes back to requests later
                    connection = await connect(Settings().rabbitmq_url)
                    async with connection:
                        channel = await connection.channel()
                        await schedule_retry(
                            channel,
                            org,
                            p,
                            delay_ms=decision.delay_ms,
                            logical_priority=decision.next_priority,
                        )
                    # Metrics: policy + demotion
                    RETRY_POLICY_TOTAL.labels(strategy=str(decision.strategy), error_type=str(decision.error_type)).inc()
                    if decision.next_priority != old_priority:
                        RETRY_DEMOTION_TOTAL.labels(from=f"P{old_priority}", to=f"P{decision.next_priority}").inc()
                    await audit_failed_then_retry(
                        p,
                        org,
                        exc,
                        int(p["retry_count"]),
                        decision.delay_ms,
                        demotion_from=old_priority,
                        demotion_to=decision.next_priority,
                        strategy=str(decision.strategy),
                        error_type=str(decision.error_type),
                    )
                    WORKER_RETRY_TOTAL.labels(type=p.get("type")).inc()
                else:
                    # Terminal failure: ship to DLQ and record audit entries
                    connection = await connect(Settings().rabbitmq_url)
                    async with connection:
                        channel = await connection.channel()
                        await publish_to_dlq(channel, org, p)
                    await audit_dead_letter(p, org, exc)
                    WORKER_DLQ_TOTAL.labels(type=p.get("type")).inc()
            finally:
                WORKER_PROCESS_LATENCY_SECONDS.observe(time.perf_counter() - start_ts)

    async def _emit_result(self, orig: dict[str, Any], result: Any) -> None:
        """Publish the final result for a processed message to the agent response queue."""
        payload = {
            "request_id": orig.get("message_id"),
            "type": "result",
            "result": result,
            "timestamp": orig.get("created_at"),
        }
        connection = await connect(Settings().rabbitmq_url)
        async with connection:
            channel = await connection.channel()
            await publish_response(channel, self.agent_id, payload)
            print(f"Worker emitted result for {orig.get('message_id')} -> agent {self.agent_id}")

    async def _emit_error(self, message: AbstractIncomingMessage, exc: Exception) -> None:
        """Publish an error response for the current message to the agent response queue."""
        try:
            payload = json.loads(message.body)
            request_id = payload.get("message_id")
        except Exception:  # noqa: BLE001
            request_id = None
        error_payload = {
            "request_id": request_id,
            "type": "error",
            "error": {
                "type": exc.__class__.__name__,
                "message": str(exc),
            },
        }
        connection = await connect(Settings().rabbitmq_url)
        async with connection:
            channel = await connection.channel()
            await publish_response(channel, self.agent_id, error_payload)
            print(f"Worker emitted error for {request_id} -> agent {self.agent_id}")

    async def handle_agent_message(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Example business logic for an agent-local message type.

        Replace this with real handlers as you introduce tool/model/memory ops.
        """
        await asyncio.sleep(0.05)
        return {"echo": payload.get("context", {})}

    async def handle_passthrough(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Stub handler used for message types not yet implemented."""
        await asyncio.sleep(0.05)
        return {"status": "ok", "type": payload.get("type")}

    async def handle_unknown(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Fallback handler when no registered handler exists for the message type."""
        return {"status": "unknown_type", "type": payload.get("type")}

    def stop(self) -> None:
        """Signal the run loop to stop (used by signal handlers)."""
        self._stopping.set()


async def main() -> None:
    """Entrypoint for running a worker as a script."""
    org_id = os.getenv("ORG_ID", "demo-org")
    agent_id = os.getenv("AGENT_ID", "demo-agent")
    worker = Worker(org_id, agent_id)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, worker.stop)

    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())


