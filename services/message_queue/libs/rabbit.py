"""RabbitMQ helpers for connections, topology, and publishing.

This module wraps ``aio_pika`` to provide a consistent interface for:
- Establishing robust connections with optional TLS/mTLS support
- Declaring per-organization request, retry, and DLQ topologies
- Declaring per-agent response topologies
- Publishing requests, retries, responses, and DLQ messages

All functions are typed and documented with examples for clarity.
"""

import json
import os
import asyncio
import ssl
from typing import Optional, Any, Mapping, Dict
from urllib.parse import urlsplit

import aio_pika
from aio_pika import ExchangeType, Message, DeliveryMode
from aio_pika.abc import AbstractChannel, AbstractRobustConnection, HeadersType

from libs.config import (
    map_logical_priority_to_amqp,
    Settings,
)


PRIORITY_LEVELS = 10  # x-max-priority


def _build_ssl_context(settings: Settings) -> Optional[ssl.SSLContext]:
    """Return an ``ssl.SSLContext`` for TLS/mTLS if configured, else ``None``.

    Honors ``RABBITMQ_SSL_*`` flags in ``Settings``. When verification is
    disabled (dev/local), hostname checks and certificate verification are
    relaxed.
    """
    scheme = urlsplit(settings.rabbitmq_url).scheme.lower()
    wants_tls = scheme == "amqps" or any(
        [
            bool(settings.rabbitmq_ssl_ca_path),
            bool(settings.rabbitmq_ssl_cert_path),
            bool(settings.rabbitmq_ssl_key_path),
        ]
    )
    if not wants_tls:
        return None

    # Create default context, optionally disabling verification for dev
    cafile = settings.rabbitmq_ssl_ca_path or None
    context = ssl.create_default_context(cafile=cafile)

    # Client certs for mTLS if provided
    if settings.rabbitmq_ssl_cert_path and settings.rabbitmq_ssl_key_path:
        context.load_cert_chain(settings.rabbitmq_ssl_cert_path, settings.rabbitmq_ssl_key_path)

    # Verification and hostname checks
    if not settings.rabbitmq_ssl_verify:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    else:
        context.check_hostname = bool(settings.rabbitmq_ssl_check_hostname)
        context.verify_mode = ssl.CERT_REQUIRED

    return context


async def connect(amqp_url: str | None = None) -> AbstractRobustConnection:
    """Create a robust AMQP connection with optional TLS/mTLS and retry/backoff.

    Why:
    - RabbitMQ may not be immediately ready in CI/local; a bounded retry loop
      reduces flakiness during topology initialization and tests.

    Environment overrides:
    - ``RABBITMQ_CONNECT_ATTEMPTS`` (default: 12)
    - ``RABBITMQ_CONNECT_BASE_DELAY_MS`` (default: 500)
    - ``RABBITMQ_CONNECT_MAX_DELAY_MS`` (default: 3000)

    Example:
        >>> conn = await connect()
        >>> async with conn:
        ...     channel = await conn.channel()
    """
    settings = Settings()
    url = amqp_url or settings.rabbitmq_url
    ssl_context = _build_ssl_context(settings)

    max_attempts = int(os.getenv("RABBITMQ_CONNECT_ATTEMPTS", "12"))
    delay_ms = int(os.getenv("RABBITMQ_CONNECT_BASE_DELAY_MS", "500"))
    max_delay_ms = int(os.getenv("RABBITMQ_CONNECT_MAX_DELAY_MS", "3000"))

    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            if ssl_context is not None:
                # Underlying aiormq expects SSLOptions-type; our context aligns but stubs complain
                return await aio_pika.connect_robust(url, ssl=True, ssl_options=ssl_context)  # type: ignore[arg-type]
            return await aio_pika.connect_robust(url)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt == max_attempts:
                break
            await asyncio.sleep(delay_ms / 1000.0)
            delay_ms = min(int(delay_ms * 2), max_delay_ms)
    assert last_exc is not None
    raise last_exc


async def declare_org_topology(channel: AbstractChannel, org_id: str) -> None:
    """Declare per-org request exchange/queue and DLQ exchange/queue.

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
    """Declare per-agent response exchange and queue for the given agent id."""
    resp_exchange_name = f"agent.{agent_id}.responses"
    resp_queue_name = f"agent.{agent_id}.responses.q"

    resp_exchange = await channel.declare_exchange(resp_exchange_name, ExchangeType.DIRECT, durable=True)
    resp_queue = await channel.declare_queue(resp_queue_name, durable=True)
    await resp_queue.bind(resp_exchange, routing_key="responses")


async def publish_request(
    channel: AbstractChannel,
    org_id: str,
    message: Mapping[str, Any],
    logical_priority: int,
    headers: Optional[HeadersType] = None,
    persistent: bool = True,
) -> None:
    """Publish a request to the org exchange with AMQP priority.

    Uses the given channel. Callers can enable publisher confirms on the
    channel for reliability and set ``mandatory=True``.
    """
    exchange = await channel.get_exchange(f"org.{org_id}.requests")
    amqp_priority = map_logical_priority_to_amqp(logical_priority)
    body = json.dumps(message, separators=(",", ":")).encode("utf-8")
    # Ensure headers are a plain dict for type checker
    hdrs: Dict[str, Any] = dict(headers) if headers else {}
    amqp_message = Message(
        body=body,
        content_type="application/json",
        delivery_mode=DeliveryMode.PERSISTENT if persistent else DeliveryMode.NOT_PERSISTENT,
        priority=amqp_priority,
        headers=hdrs,
    )
    await exchange.publish(amqp_message, routing_key="requests", mandatory=True)


async def publish_response(
    channel: AbstractChannel,
    agent_id: str,
    payload: Mapping[str, Any],
    headers: Optional[HeadersType] = None,
    persistent: bool = True,
) -> None:
    """Publish a response payload to the agent's response exchange."""
    exchange = await channel.get_exchange(f"agent.{agent_id}.responses")
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    hdrs: Dict[str, Any] = dict(headers) if headers else {}
    amqp_message = Message(
        body=body,
        content_type="application/json",
        delivery_mode=DeliveryMode.PERSISTENT if persistent else DeliveryMode.NOT_PERSISTENT,
        headers=hdrs,
    )
    await exchange.publish(amqp_message, routing_key="responses")


async def declare_org_retry_topology(channel: AbstractChannel, org_id: str, delays_ms: list[int] | None = None) -> None:
    """Declare retry exchange and per-delay queues that DLX back to requests.

    Each delay queue holds the message for ``x-message-ttl`` milliseconds and
    then dead-letters it back to the org's requests exchange.
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
    message: Mapping[str, Any],
    delay_ms: int,
    logical_priority: int,
    headers: Optional[HeadersType] = None,
) -> None:
    """Send a failed message to the per-org retry exchange for future redelivery."""
    exchange = await channel.get_exchange(f"org.{org_id}.retry")
    amqp_priority = map_logical_priority_to_amqp(logical_priority)
    body = json.dumps(message, separators=(",", ":")).encode("utf-8")
    hdrs: Dict[str, Any] = dict(headers) if headers else {}
    amqp_message = Message(
        body=body,
        content_type="application/json",
        delivery_mode=DeliveryMode.PERSISTENT,
        priority=amqp_priority,
        headers=hdrs,
    )
    await exchange.publish(amqp_message, routing_key=f"delay_{delay_ms}")


async def publish_to_dlq(
    channel: AbstractChannel,
    org_id: str,
    message: Mapping[str, Any],
    headers: Optional[HeadersType] = None,
) -> None:
    """Publish a terminal failure to the org DLQ exchange."""
    dlx = await channel.get_exchange(f"org.{org_id}.dlx")
    body = json.dumps(message, separators=(",", ":")).encode("utf-8")
    amqp_message = Message(
        body=body,
        content_type="application/json",
        delivery_mode=DeliveryMode.PERSISTENT,
        headers=dict(headers) if headers else {},
    )
    await dlx.publish(amqp_message, routing_key="dead")


async def publish_requests_batch(
    channel: AbstractChannel,
    org_id: str,
    items: list[dict[str, Any]],
    persistent: bool = True,
) -> None:
    """Publish a batch of request messages efficiently on a single channel.

    Each item dict must have: {"message": dict, "priority": int, "headers": Optional[dict]}
    """
    exchange = await channel.get_exchange(f"org.{org_id}.requests")
    for item in items:
        msg = item["message"]
        logical_priority = int(item.get("priority", 2))
        hdrs: Dict[str, Any] = dict(item.get("headers") or {})
        amqp_priority = map_logical_priority_to_amqp(logical_priority)
        body = json.dumps(msg, separators=(",", ":")).encode("utf-8")
        amqp_message = Message(
            body=body,
            content_type="application/json",
            delivery_mode=DeliveryMode.PERSISTENT if persistent else DeliveryMode.NOT_PERSISTENT,
            priority=amqp_priority,
            headers=hdrs,
        )
        await exchange.publish(amqp_message, routing_key="requests", mandatory=True)


