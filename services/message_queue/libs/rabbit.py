import json
from typing import Optional

import aio_pika
from aio_pika import ExchangeType, Message, DeliveryMode
from aio_pika.abc import AbstractChannel

from libs.config import map_logical_priority_to_amqp


PRIORITY_LEVELS = 10  # x-max-priority


async def connect(amqp_url: str) -> aio_pika.RobustConnection:
    """Create a robust AMQP connection (auto-reconnect)."""
    return await aio_pika.connect_robust(amqp_url)


async def declare_org_topology(channel: AbstractChannel, org_id: str) -> None:
    """Declare request exchange/queue and DLQ for a single organization.

    - Requests: direct exchange bound to a single priority queue
    - DLQ: direct exchange and queue for terminal failures
    """
    # Requests
    req_exchange_name = f"org.{org_id}.requests"
    req_queue_name = f"org.{org_id}.requests.q"

    req_exchange = await channel.declare_exchange(req_exchange_name, ExchangeType.DIRECT, durable=True)
    await channel.declare_queue(
        req_queue_name,
        durable=True,
        arguments={"x-max-priority": PRIORITY_LEVELS},
    )
    queue = await channel.get_queue(req_queue_name)
    await queue.bind(req_exchange, routing_key="requests")

    # DLQ
    dlx_name = f"org.{org_id}.dlx"
    dlq_name = f"org.{org_id}.dlq"
    dlx = await channel.declare_exchange(dlx_name, ExchangeType.DIRECT, durable=True)
    dlq = await channel.declare_queue(dlq_name, durable=True)
    await dlq.bind(dlx, routing_key="dead")


async def declare_agent_response_topology(channel: AbstractChannel, agent_id: str) -> None:
    """Declare per-agent response exchange and queue."""
    resp_exchange_name = f"agent.{agent_id}.responses"
    resp_queue_name = f"agent.{agent_id}.responses.q"

    resp_exchange = await channel.declare_exchange(resp_exchange_name, ExchangeType.DIRECT, durable=True)
    resp_queue = await channel.declare_queue(resp_queue_name, durable=True)
    await resp_queue.bind(resp_exchange, routing_key="responses")


async def publish_request(
    channel: AbstractChannel,
    org_id: str,
    message: dict,
    logical_priority: int,
    headers: Optional[dict] = None,
    persistent: bool = True,
) -> None:
    """Publish a request to the org exchange with AMQP priority.

    Uses the given channel; caller can enable confirms on the channel for
    reliability (publisher confirms), and set mandatory flag if desired.
    """
    exchange = await channel.get_exchange(f"org.{org_id}.requests")
    amqp_priority = map_logical_priority_to_amqp(logical_priority)
    body = json.dumps(message, separators=(",", ":")).encode("utf-8")
    amqp_message = Message(
        body=body,
        content_type="application/json",
        delivery_mode=DeliveryMode.PERSISTENT if persistent else DeliveryMode.NOT_PERSISTENT,
        priority=amqp_priority,
        headers=headers or {},
    )
    await exchange.publish(amqp_message, routing_key="requests", mandatory=True)


async def publish_response(
    channel: AbstractChannel,
    agent_id: str,
    payload: dict,
    headers: Optional[dict] = None,
    persistent: bool = True,
) -> None:
    """Publish a response payload to the agent's response exchange."""
    exchange = await channel.get_exchange(f"agent.{agent_id}.responses")
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    amqp_message = Message(
        body=body,
        content_type="application/json",
        delivery_mode=DeliveryMode.PERSISTENT if persistent else DeliveryMode.NOT_PERSISTENT,
        headers=headers or {},
    )
    await exchange.publish(amqp_message, routing_key="responses")


async def declare_org_retry_topology(channel: AbstractChannel, org_id: str, delays_ms: list[int] | None = None) -> None:
    """Declare retry exchange and per-delay queues that DLX back to requests.

    Each delay queue holds the message for `x-message-ttl` milliseconds and then
    dead-letters it back to the org's requests exchange.
    """
    if delays_ms is None:
        delays_ms = [1000, 2000, 4000, 8000]

    req_exchange_name = f"org.{org_id}.requests"
    retry_exchange_name = f"org.{org_id}.retry"

    retry_exchange = await channel.declare_exchange(retry_exchange_name, ExchangeType.DIRECT, durable=True)

    for delay in delays_ms:
        qname = f"org.{org_id}.retry.{delay}"
        # Messages wait here until TTL then DLX back to requests
        queue = await channel.declare_queue(
            qname,
            durable=True,
            arguments={
                "x-message-ttl": delay,
                "x-dead-letter-exchange": req_exchange_name,
                "x-dead-letter-routing-key": "requests",
            },
        )
        await queue.bind(retry_exchange, routing_key=f"delay_{delay}")


async def schedule_retry(
    channel: AbstractChannel,
    org_id: str,
    message: dict,
    delay_ms: int,
    logical_priority: int,
    headers: Optional[dict] = None,
) -> None:
    """Send a failed message to the per-org retry exchange for a future redelivery."""
    exchange = await channel.get_exchange(f"org.{org_id}.retry")
    amqp_priority = map_logical_priority_to_amqp(logical_priority)
    body = json.dumps(message, separators=(",", ":")).encode("utf-8")
    amqp_message = Message(
        body=body,
        content_type="application/json",
        delivery_mode=DeliveryMode.PERSISTENT,
        priority=amqp_priority,
        headers=headers or {},
    )
    await exchange.publish(amqp_message, routing_key=f"delay_{delay_ms}")


async def publish_to_dlq(
    channel: AbstractChannel,
    org_id: str,
    message: dict,
    headers: Optional[dict] = None,
) -> None:
    """Publish a terminal failure to the org DLQ exchange."""
    dlx = await channel.get_exchange(f"org.{org_id}.dlx")
    body = json.dumps(message, separators=(",", ":")).encode("utf-8")
    amqp_message = Message(
        body=body,
        content_type="application/json",
        delivery_mode=DeliveryMode.PERSISTENT,
        headers=headers or {},
    )
    await dlx.publish(amqp_message, routing_key="dead")


async def publish_requests_batch(
    channel: AbstractChannel,
    org_id: str,
    items: list[dict],
    persistent: bool = True,
) -> None:
    """Publish a batch of request messages efficiently on a single channel.

    Each item dict must have: {"message": dict, "priority": int, "headers": Optional[dict]}
    """
    exchange = await channel.get_exchange(f"org.{org_id}.requests")
    for item in items:
        msg = item["message"]
        logical_priority = int(item.get("priority", 2))
        headers = item.get("headers") or {}
        amqp_priority = map_logical_priority_to_amqp(logical_priority)
        body = json.dumps(msg, separators=(",", ":")).encode("utf-8")
        amqp_message = Message(
            body=body,
            content_type="application/json",
            delivery_mode=DeliveryMode.PERSISTENT if persistent else DeliveryMode.NOT_PERSISTENT,
            priority=amqp_priority,
            headers=headers,
        )
        await exchange.publish(amqp_message, routing_key="requests", mandatory=True)


