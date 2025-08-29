from __future__ import annotations

import math
import time
from typing import List

from .graph import GraphClient


def temporal_decay(ts_ms: int, now_ms: int | None = None, half_life_seconds: int = 3600) -> float:
    now = now_ms or int(time.time() * 1000)
    age_s = max(0.0, (now - ts_ms) / 1000.0)
    return 0.5 ** (age_s / half_life_seconds)


def expire_ephemeral(graph: GraphClient, ttl_seconds: int | None = None) -> int:
    return graph.expire_ephemeral(ttl_seconds=ttl_seconds)


def resolve_text_conflict(a: str, b: str) -> str:
    # Simple heuristic placeholder: pick longer text
    return a if len(a) >= len(b) else b
