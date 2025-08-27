from __future__ import annotations

from typing import Any, Dict

try:
    import aio_pika  # type: ignore
except Exception:  # pragma: no cover
    aio_pika = None  # type: ignore

from .config import RABBITMQ_URL


async def publish(task_type: str, payload: Dict[str, Any]) -> None:
    if aio_pika is None:
        return
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    try:
        channel = await connection.channel()
        exchange = await channel.declare_exchange("ctx.v2", aio_pika.ExchangeType.DIRECT)
        await exchange.publish(aio_pika.Message(body=str(payload).encode("utf-8")), routing_key=task_type)
    finally:
        await connection.close()
