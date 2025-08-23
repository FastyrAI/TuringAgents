"""Backpressure utilities based on RabbitMQ queue depth via management API.

This module polls the queue depth and decides when to signal throttle modes.
"""

from __future__ import annotations

import os
from typing import Literal, Tuple

import httpx


ThrottleMode = Literal["none", "light", "heavy", "emergency"]


class BackpressureConfig:
    def __init__(
        self,
        scale_threshold: int = 100,
        light_throttle_threshold: int = 500,
        heavy_throttle_threshold: int = 1000,
        emergency_threshold: int = 5000,
    ) -> None:
        self.scale_threshold = scale_threshold
        self.light_throttle_threshold = light_throttle_threshold
        self.heavy_throttle_threshold = heavy_throttle_threshold
        self.emergency_threshold = emergency_threshold


def get_queue_depth(org_id: str) -> int:
    """Fetch the current queue depth via RabbitMQ management API.

    Requires RabbitMQ management UI to be enabled and accessible at RABBITMQ_MGMT_URL,
    with credentials RABBITMQ_USER / RABBITMQ_PASS.
    """
    base = os.getenv("RABBITMQ_MGMT_URL", "http://localhost:15672")
    user = os.getenv("RABBITMQ_USER", "guest")
    pw = os.getenv("RABBITMQ_PASS", "guest")
    vhost = "%2F"
    qname = f"org.{org_id}.requests.q"
    url = f"{base}/api/queues/{vhost}/{qname}"
    try:
        r = httpx.get(url, auth=(user, pw), timeout=5)
        if r.status_code != 200:
            return 0
        data = r.json()
        return int(data.get("messages", 0))
    except Exception:
        return 0


def decide_throttle(depth: int, cfg: BackpressureConfig) -> ThrottleMode:
    """Return throttle mode based on depth thresholds."""
    if depth > cfg.emergency_threshold:
        return "emergency"
    if depth > cfg.heavy_throttle_threshold:
        return "heavy"
    if depth > cfg.light_throttle_threshold:
        return "light"
    return "none"


