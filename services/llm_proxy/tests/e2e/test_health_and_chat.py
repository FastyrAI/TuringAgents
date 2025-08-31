"""
End-to-end tests for the LiteLLM proxy.

These tests assume the proxy is running locally via Docker Compose on http://localhost:4000
and that a valid `LITELLM_MASTER_KEY` is available.

Usage examples:
  $ docker compose -f docker-compose.yml -f services/llm_proxy/compose/docker-compose.override.yml --env-file services/llm_proxy/.env up -d
  $ cd services/llm_proxy && pip install -e .[test]
  $ pytest -q tests/e2e
"""

import os
import time
from typing import Dict, Any

import httpx


BASE_URL = os.environ.get("LITELLM_BASE_URL", "http://localhost:4000")
MASTER_KEY = os.environ.get("LITELLM_MASTER_KEY", "sk-dev-1234")


def wait_for_health(timeout_seconds: int = 60) -> None:
    """Poll the health endpoint until it returns HTTP 200 or timeout.

    This helps absorb startup time for the DB and Redis containers on compose up.
    """
    deadline = time.time() + timeout_seconds
    last_status = None
    while time.time() < deadline:
        try:
            resp = httpx.get(f"{BASE_URL}/health", timeout=5.0)
            last_status = resp.status_code
            if resp.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(2)
    raise AssertionError(f"Health endpoint did not return 200 within {timeout_seconds}s (last={last_status})")


def test_health_endpoints() -> None:
    """Verify health endpoints respond with 200."""
    wait_for_health()
    r1 = httpx.get(f"{BASE_URL}/health", timeout=10.0)
    r2 = httpx.get(f"{BASE_URL}/health/readiness", timeout=10.0)
    r3 = httpx.get(f"{BASE_URL}/health/liveness", timeout=10.0)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 200


def test_chat_completions_basic() -> None:
    """Make a simple chat completion call and validate response shape."""
    wait_for_health()
    headers: Dict[str, str] = {
        "Authorization": f"Bearer {MASTER_KEY}",
        "Content-Type": "application/json",
    }
    payload: Dict[str, Any] = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "Say hello"}],
    }
    resp = httpx.post(
        f"{BASE_URL}/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=30.0,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "id" in body
    assert "choices" in body and isinstance(body["choices"], list) and body["choices"]
    msg = body["choices"][0].get("message", {})
    assert msg.get("role") in {"assistant", "system"}
