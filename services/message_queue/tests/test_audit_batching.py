import asyncio
import types

import pytest

from libs.audit import AuditEventBatcher


@pytest.mark.asyncio
async def test_batch_flushes_on_size(monkeypatch):
    written = []

    batcher = AuditEventBatcher(batch_size=5, flush_interval_ms=10_000, queue_max=100)

    async def fake_write(items):
        written.append(list(items))

    batcher._write_batch = types.MethodType(lambda self, items: fake_write(items), batcher)  # type: ignore
    batcher.start()

    for i in range(5):
        await batcher.enqueue({"org_id": "o", "event_type": "created", "details": {"i": i}})

    # Give the loop a tick to process the size-triggered flush
    await asyncio.sleep(0.05)

    assert len(written) == 1
    assert len(written[0]) == 5


@pytest.mark.asyncio
async def test_batch_flushes_on_interval(monkeypatch):
    written = []

    batcher = AuditEventBatcher(batch_size=10, flush_interval_ms=50, queue_max=100)

    async def fake_write(items):
        written.append(list(items))

    batcher._write_batch = types.MethodType(lambda self, items: fake_write(items), batcher)  # type: ignore
    batcher.start()

    for i in range(3):
        await batcher.enqueue({"org_id": "o", "event_type": "created", "details": {"i": i}})

    # Wait longer than interval to force a timer-based flush
    await asyncio.sleep(0.1)

    assert len(written) >= 1
    assert sum(len(b) for b in written) >= 3

