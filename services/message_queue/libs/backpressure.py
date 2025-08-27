"""Backpressure utilities based on RabbitMQ queue depth via management API.

This module queries the queue depth of an organization's priority queue using
the RabbitMQ Management HTTP API and provides a simple policy to map depth to
throttle modes. Callers can use these signals to shed load at the producer or
to scale workers.

Usage example:
    >>> depth = get_queue_depth("demo-org")
    >>> mode = decide_throttle(depth, BackpressureConfig())
    >>> mode in {"none", "light", "heavy", "emergency"}
    True
"""

from __future__ import annotations

import os
from typing import Literal, Tuple

import httpx


ThrottleMode = Literal["none", "light", "heavy", "emergency"]


class BackpressureConfig:
    """Thresholds controlling throttle modes derived from queue depth.

    Attributes:
        scale_threshold: Depth at which autoscaling should be considered.
        light_throttle_threshold: Depth at which to throttle lowest-priority traffic.
        heavy_throttle_threshold: Depth at which to throttle mid/low priority.
        emergency_threshold: Depth at which to allow only P0 traffic.

    Example:
        >>> cfg = BackpressureConfig(light_throttle_threshold=200)
        >>> decide_throttle(50, cfg)
        'none'
        >>> decide_throttle(5000, cfg)
        'emergency'
    """

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
    """Return current queue depth via RabbitMQ Management API.

    Requires RabbitMQ Management to be enabled and reachable at ``RABBITMQ_MGMT_URL``.
    Credentials are read from ``RABBITMQ_USER``/``RABBITMQ_PASS``. On any error,
    returns 0 to fail-open.
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
    """Map a queue depth to a throttle mode using the provided thresholds.

    Returns one of: ``"none"``, ``"light"``, ``"heavy"``, ``"emergency"``.
    """
    if depth > cfg.emergency_threshold:
        return "emergency"
    if depth > cfg.heavy_throttle_threshold:
        return "heavy"
    if depth > cfg.light_throttle_threshold:
        return "light"
    return "none"


