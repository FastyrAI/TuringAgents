"""Retry policy helpers.

Encapsulates how we choose the next delay (ms) for a given retry count.
"""
from __future__ import annotations

from typing import List
import random

from libs.constants import DEFAULT_RETRY_DELAYS_MS


def next_delay_ms(retry_count: int, delays: List[int] | None = None, jitter: float = 0.0) -> int:
    """Return the next delay in milliseconds for a given retry attempt.

    The `retry_count` is zero-based (first retry has retry_count == 0).
    Falls back to the last provided delay if `retry_count` exceeds bounds.
    """
    if delays is None:
        delays = DEFAULT_RETRY_DELAYS_MS
    idx = max(min(retry_count, len(delays) - 1), 0)
    base = delays[idx]
    # Add small jitter (+/- jitter%) to avoid thundering herd
    if jitter <= 0:
        return int(base)
    delta = base * jitter
    return int(random.uniform(base - delta, base + delta))


