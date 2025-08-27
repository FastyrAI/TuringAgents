"""
Agent Coordinator.

- Maintains a single RabbitMQ connection per server
- Subscribes to per-agent response queues
- Routes responses to local agents (here, a simple in-memory queue per agent)
- Prints demo-agent responses to stdout for observability
"""

import asyncio
import json
import os
from typing import Dict

import aio_pika
from aio_pika.abc import AbstractIncomingMessage

from libs.config import Settings
from libs.rabbit import declare_agent_response_topology, connect
from libs.tracing import start_tracing, get_tracer, extract_context_from_headers
from opentelemetry import context  # type: ignore
from libs.metrics import COORDINATOR_FORWARDED_TOTAL


class AgentCoordinator:
    """Fan-in of agent responses for all local agents on this server."""

    def __init__(self) -> None:
        self.local_agents: Dict[str, asyncio.Queue[dict[str, object]]] = {}

    async def run(self) -> None:
        """Open a connection and subscribe to each local agent's response queue."""
        start_tracing("ta-coordinator")
        self._tracer = get_tracer("ta-coordinator")
        settings = Settings()
        connection = await connect(settings.rabbitmq_url)
        async with connection:
            channel = await connection.channel()
            # Pre-declare known agents (env var list)
            for agent_id in os.getenv("AGENT_IDS", "demo-agent").split(","):
                await declare_agent_response_topology(channel, agent_id)
                self.local_agents[agent_id] = asyncio.Queue(maxsize=1000)
                queue = await channel.get_queue(f"agent.{agent_id}.responses.q")
                print(f"Coordinator subscribing to agent responses for {agent_id}")
                await queue.consume(lambda msg, a=agent_id: self._on_message(a, msg), no_ack=True)

            # Demo: read from demo-agent queue and print
            if "demo-agent" in self.local_agents:
                print("Coordinator listening for demo-agent responses...")
                while True:
                    payload = await self.local_agents["demo-agent"].get()
                    print("[demo-agent response]", json.dumps(payload))

    async def _on_message(self, agent_id: str, message: AbstractIncomingMessage) -> None:
        """Push the response payload to the agent's in-memory queue."""
        try:
            payload: dict[str, object]
            payload = json.loads(message.body)
        except Exception:  # noqa: BLE001
            payload = {"malformed": True}
        ctx = extract_context_from_headers(message.headers)
        token = context.attach(ctx)
        try:
            with self._tracer.start_as_current_span("forward_response") as span:
                span.set_attribute("agent_id", agent_id)
                rid = payload.get("request_id") if isinstance(payload.get("request_id"), (str, int)) else None
                if rid is not None:
                    span.set_attribute("request_id", rid)
                await self.local_agents[agent_id].put(payload)
                # increment forwarded metric by response type (if present)
                resp_type = payload.get("type") if isinstance(payload.get("type"), str) else "unknown"
                COORDINATOR_FORWARDED_TOTAL.labels(type=resp_type).inc()
        finally:
            context.detach(token)
        print(f"Coordinator routed response for {agent_id}: {payload.get('request_id')}")


async def main() -> None:
    coordinator = AgentCoordinator()
    await coordinator.run()


if __name__ == "__main__":
    asyncio.run(main())


