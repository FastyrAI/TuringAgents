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
from libs.retry import next_delay_ms
from libs.constants import DEFAULT_RETRY_DELAYS_MS
from libs.metrics import (
    start_metrics_server,
    WORKER_MESSAGE_TOTAL,
    WORKER_PROCESS_LATENCY_SECONDS,
    WORKER_RETRY_TOTAL,
    WORKER_DLQ_TOTAL,
    QUEUE_DEPTH,
    WORKER_RESPONSE_PUBLISHED_TOTAL,
    STREAM_CHUNK_PUBLISHED_TOTAL,
)
from libs.backpressure import get_queue_depth
from libs.dedup import compute_dedup_key, mark_and_check
from libs.constants import EVENT_DUPLICATE_SKIPPED, STATUS_DUPLICATE
from libs.tracing import start_tracing, get_tracer, extract_context_from_headers
from opentelemetry import context  # type: ignore
from libs.poison import increment_failure, should_quarantine
from libs.audit import record_message_event, upsert_message  # type: ignore
from libs.response_payloads import (
    build_acknowledgment_payload,
    build_progress_payload,
    build_stream_chunk_payload,
    build_stream_complete_payload,
    build_result_payload,
    build_error_payload,
)


Handler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class Worker:
    """Asynchronous message worker scoped to a single organization.

    Purpose:
    - Consume the organization's priority request queue and process messages
    - Emit responses to per-agent response queues
    - Handle retries, DLQ, metrics and tracing

    Concurrency model:
    - Concurrency is bounded by two independent knobs:
      1) `WORKER_PREFETCH` (AMQP QoS): how many messages the broker will deliver without ack
      2) `WORKER_CONCURRENCY` (semaphore): max number of in-flight message handlers per worker process
    - Effective concurrency is `min(WORKER_PREFETCH, WORKER_CONCURRENCY)`
    - Ordering is best-effort only; agents must self-serialize when required

    Response routing:
    - Responses are routed to `agent.<agent_id>.responses` based on the message payload's `agent_id`
      (fallback to the worker's `agent_id` when payload is missing the field for backward compatibility).

    Example:
    ```python
    # Run a worker locally with higher throughput
    os.environ["WORKER_PREFETCH"] = "32"
    os.environ["WORKER_CONCURRENCY"] = "16"
    await Worker(org_id="demo-org", agent_id="demo-agent").run()
    ```
    Properties:
    - `org_id`: Organization whose request queue this worker consumes
    - `agent_id`: Default agent id used for routing/audit when payload agent is missing
    - `retry_delays`: Exponential backoff schedule in milliseconds
    - Internal semaphore and per-agent declaration cache
    """

    def __init__(self, org_id: str, agent_id: str):
        self.org_id = org_id
        self.agent_id = agent_id
        self._stopping = asyncio.Event()
        # Exponential backoff delays; can be configured per deployment
        self.retry_delays = DEFAULT_RETRY_DELAYS_MS
        # Set at runtime in run() when settings are available
        self._sem: asyncio.Semaphore | None = None
        # Cache of agents whose response topology has been declared in this process
        self._declared_agents: set[str] = set()
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
        """Connect to RabbitMQ and begin consuming the org queue.

        Starts metrics and tracing, sets QoS/prefetch and configures a concurrency
        semaphore to bound in-flight message handlers.
        """
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

        # Initialize concurrency semaphore
        self._sem = asyncio.Semaphore(settings.worker_concurrency)

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
            self._declared_agents.add(self.agent_id)

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
        """Core processing lifecycle for a single message.

        Uses a semaphore to enforce `WORKER_CONCURRENCY` in-flight handlers.
        """
        # Guard: ensure semaphore is initialized
        if self._sem is None:
            self._sem = asyncio.Semaphore(1)

        await self._sem.acquire()
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

                # Emit acknowledgment immediately so agents can reflect progress
                await self._emit_acknowledgment(payload)

                # Use incoming trace context from headers to continue the trace
                ctx = extract_context_from_headers(message.headers)
                token = context.attach(ctx)
                try:
                    with self._tracer.start_as_current_span("process") as span:
                        span.set_attribute("message_id", payload.get("message_id"))
                        span.set_attribute("org_id", self.org_id)
                        # Optional progress demo
                        context_map = payload.get("context", {}) or {}
                        progress_updates = context_map.get("progress_updates")
                        if progress_updates and isinstance(progress_updates, (list, tuple)):
                            for p in progress_updates:
                                try:
                                    await self._emit_progress(payload, int(p), status="working")
                                except Exception:
                                    # Best-effort progress
                                    pass
                        elif context_map.get("progress_demo"):
                            await self._emit_progress(payload, 50, status="halfway")

                        # Execute handler
                        result = await handler(payload)

                        # Optional streaming demo: emit chunks instead of a single result
                        if context_map.get("stream_demo"):
                            chunks = context_map.get("stream_chunks")
                            if not isinstance(chunks, (list, tuple)):
                                chunks = ["chunk-0", "chunk-1"]
                            for idx, chunk in enumerate(chunks):
                                await self._emit_stream_chunk(payload, chunk, idx)
                            await self._emit_stream_complete(payload, total_chunks=len(chunks))
                        else:
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

                retry_count = int(p.get("retry_count", 0))
                max_retries = int(p.get("max_retries", 3))
                p["retry_count"] = retry_count + 1
                org = p.get("org_id", self.org_id)

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

                if retry_count < max_retries:
                    delay = next_delay_ms(retry_count, self.retry_delays)
                    # Publish to delay queue so it DLXes back to requests later
                    connection = await connect(Settings().rabbitmq_url)
                    async with connection:
                        channel = await connection.channel()
                        await schedule_retry(
                            channel,
                            org,
                            p,
                            delay_ms=delay,
                            logical_priority=int(p.get("priority", 2)),
                        )
                    await audit_failed_then_retry(p, org, exc, int(p["retry_count"]), delay)
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
                # Release concurrency slot
                try:
                    self._sem.release()
                except Exception:
                    pass

    async def _emit_result(self, orig: dict[str, Any], result: Any) -> None:
        """Publish a non-streaming result to the agent response queue.

        Why: Completes simple operations that don't need streaming.

        Example usage:
            await self._emit_result(orig_payload, {"ok": True})
        """
        payload = build_result_payload(orig, result)
        connection = await connect(Settings().rabbitmq_url)
        async with connection:
            channel = await connection.channel()
            dest_agent = self._get_dest_agent(orig)
            await self._ensure_response_topology(channel, dest_agent)
            await publish_response(channel, dest_agent, payload)
            print(f"Worker emitted result for {orig.get('message_id')} -> agent {dest_agent}")
        WORKER_RESPONSE_PUBLISHED_TOTAL.labels(type="result").inc()

    async def _emit_error(self, message: AbstractIncomingMessage, exc: Exception) -> None:
        """Publish an error response to the agent response queue.

        Why: Surfaces failures to agents and end users.
        """
        try:
            orig = json.loads(message.body)
        except Exception:  # noqa: BLE001
            orig = None
        error_payload = build_error_payload(orig, exc)
        connection = await connect(Settings().rabbitmq_url)
        async with connection:
            channel = await connection.channel()
            dest_agent = self._get_dest_agent(orig or {})
            await self._ensure_response_topology(channel, dest_agent)
            await publish_response(channel, dest_agent, error_payload)
            print(f"Worker emitted error for {error_payload.get('request_id')} -> agent {dest_agent}")
        WORKER_RESPONSE_PUBLISHED_TOTAL.labels(type="error").inc()

    async def _emit_acknowledgment(self, orig: dict[str, Any]) -> None:
        """Publish an acknowledgment indicating the request was received/started.

        Why: Enables responsive UIs and agent orchestration.

        Example:
            await self._emit_acknowledgment(orig)
        """
        payload = build_acknowledgment_payload(orig)
        connection = await connect(Settings().rabbitmq_url)
        async with connection:
            channel = await connection.channel()
            dest_agent = self._get_dest_agent(orig)
            await self._ensure_response_topology(channel, dest_agent)
            await publish_response(channel, dest_agent, payload)
            print(f"Worker emitted acknowledgment for {orig.get('message_id')} -> agent {dest_agent}")
        WORKER_RESPONSE_PUBLISHED_TOTAL.labels(type="acknowledgment").inc()

    async def _emit_progress(self, orig: dict[str, Any], progress_percent: int, status: str | None = None) -> None:
        """Publish a progress update for a long-running operation.

        Why: Allows UIs to render progress bars and agents to sequence tasks.
        """
        payload = build_progress_payload(orig, progress_percent, status)
        connection = await connect(Settings().rabbitmq_url)
        async with connection:
            channel = await connection.channel()
            dest_agent = self._get_dest_agent(orig)
            await self._ensure_response_topology(channel, dest_agent)
            await publish_response(channel, dest_agent, payload)
            print(f"Worker emitted progress {progress_percent}% for {orig.get('message_id')} -> agent {dest_agent}")
        WORKER_RESPONSE_PUBLISHED_TOTAL.labels(type="progress").inc()

    async def _emit_stream_chunk(self, orig: dict[str, Any], chunk: Any, chunk_index: int) -> None:
        """Publish a streaming chunk for a streaming operation.

        Why: Implements low-latency delivery of partial results.
        """
        payload = build_stream_chunk_payload(orig, chunk, chunk_index)
        connection = await connect(Settings().rabbitmq_url)
        async with connection:
            channel = await connection.channel()
            dest_agent = self._get_dest_agent(orig)
            await self._ensure_response_topology(channel, dest_agent)
            await publish_response(channel, dest_agent, payload)
            print(
                f"Worker emitted stream_chunk[{chunk_index}] for {orig.get('message_id')} -> agent {dest_agent}"
            )
        WORKER_RESPONSE_PUBLISHED_TOTAL.labels(type="stream_chunk").inc()
        STREAM_CHUNK_PUBLISHED_TOTAL.labels(agent_id=self.agent_id).inc()

    async def _emit_stream_complete(self, orig: dict[str, Any], total_chunks: int) -> None:
        """Publish a stream completion marker to signal end of streaming.

        Why: Lets agents flush buffers and mark completion without ambiguity.
        """
        payload = build_stream_complete_payload(orig, total_chunks)
        connection = await connect(Settings().rabbitmq_url)
        async with connection:
            channel = await connection.channel()
            dest_agent = self._get_dest_agent(orig)
            await self._ensure_response_topology(channel, dest_agent)
            await publish_response(channel, dest_agent, payload)
            print(
                f"Worker emitted stream_complete ({total_chunks} chunks) for {orig.get('message_id')} -> agent {dest_agent}"
            )
        WORKER_RESPONSE_PUBLISHED_TOTAL.labels(type="stream_complete").inc()

    def _get_dest_agent(self, orig: dict[str, Any]) -> str:
        """Return the target agent id for a response.

        Uses the `agent_id` in the original message payload when present, or
        falls back to this worker's default `agent_id` for backwards compatibility.

        Example:
            dest = self._get_dest_agent({"agent_id": "a1"})  # -> "a1"
        """
        try:
            return str(orig.get("agent_id") or self.agent_id)
        except Exception:
            return self.agent_id

    async def _ensure_response_topology(self, channel, agent_id: str) -> None:
        """Declare the agent response exchange/queue once per process for a given agent.

        This avoids repeated declarations and ensures idempotent setup before publishing.
        """
        if agent_id not in self._declared_agents:
            await declare_agent_response_topology(channel, agent_id)
            self._declared_agents.add(agent_id)

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


