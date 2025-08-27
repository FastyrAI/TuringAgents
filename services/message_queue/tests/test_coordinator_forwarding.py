import asyncio
import json
from types import SimpleNamespace

import pytest

from scripts.coordinator import AgentCoordinator


class DummyMessage(SimpleNamespace):
    def __init__(self, payload: dict, headers: dict | None = None):
        super().__init__(body=json.dumps(payload).encode("utf-8"), headers=headers or {})


@pytest.mark.asyncio
async def test_forwarding_puts_payload_on_queue(monkeypatch):
    c = AgentCoordinator()
    c.local_agents["a1"] = asyncio.Queue()

    # make tracer available
    c._tracer = SimpleNamespace(start_as_current_span=lambda *_a, **_k: DummySpan())

    payload = {"request_id": "m1", "type": "stream_chunk", "chunk_index": 0}
    msg = DummyMessage(payload, headers={})
    await c._on_message("a1", msg)

    got = await asyncio.wait_for(c.local_agents["a1"].get(), timeout=1)
    assert got == payload


class DummySpan:
    def __enter__(self):
        return SimpleNamespace(set_attribute=lambda *_a, **_k: None)

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

