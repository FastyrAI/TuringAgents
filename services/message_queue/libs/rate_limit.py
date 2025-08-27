from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Dict, Optional

from libs.config import Settings
from libs.metrics import RATE_LIMIT_THROTTLED_TOTAL, RATE_LIMIT_WAIT_SECONDS


@dataclass
class TokenBucketConfig:
    tokens_per_sec: float
    bucket_size: int


class TokenBucket:
    """Simple token-bucket with monotonic clock and async wait."""

    def __init__(self, tokens_per_sec: float, bucket_size: int) -> None:
        self.tokens_per_sec = max(0.0, float(tokens_per_sec))
        self.bucket_size = max(0, int(bucket_size))
        self._tokens: float = float(self.bucket_size)
        self._last_refill: float = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._last_refill = now
        if self.tokens_per_sec > 0:
            self._tokens = min(self.bucket_size, self._tokens + elapsed * self.tokens_per_sec)

    async def acquire(self) -> float:
        """Acquire one token, waiting if needed. Returns wait seconds."""
        async with self._lock:
            self._refill()
            waited_total = 0.0
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return waited_total
            # Need to wait until a full token accumulates
            if self.tokens_per_sec <= 0:
                # Unlimited if rate is 0 or negative interpreted as disabled
                return 0.0
            needed = 1.0 - self._tokens
            delay = needed / self.tokens_per_sec
            await asyncio.sleep(delay)
            waited_total += delay
            # After sleeping, take the token
            self._refill()
            self._tokens = max(0.0, self._tokens - 1.0)
            return waited_total


class AsyncRateLimiter:
    """Per-org and per-user token buckets. Org buckets apply first, then user."""

    def __init__(
        self,
        org_config: Optional[TokenBucketConfig],
        user_config: Optional[TokenBucketConfig],
    ) -> None:
        self._org_config = org_config
        self._user_config = user_config
        self._org_buckets: Dict[str, TokenBucket] = {}
        self._user_buckets: Dict[str, TokenBucket] = {}
        self._lock = asyncio.Lock()

    def _get_org_bucket(self, org_id: str) -> Optional[TokenBucket]:
        if self._org_config is None:
            return None
        b = self._org_buckets.get(org_id)
        if b is None:
            b = TokenBucket(self._org_config.tokens_per_sec, self._org_config.bucket_size)
            self._org_buckets[org_id] = b
        return b

    def _get_user_bucket(self, org_id: str, user_id: str) -> Optional[TokenBucket]:
        if self._user_config is None:
            return None
        key = f"{org_id}:{user_id}"
        b = self._user_buckets.get(key)
        if b is None:
            b = TokenBucket(self._user_config.tokens_per_sec, self._user_config.bucket_size)
            self._user_buckets[key] = b
        return b

    async def acquire(self, *, org_id: str, user_id: str) -> float:
        """Acquire tokens from org then user buckets. Returns total wait seconds."""
        waited = 0.0

        org_bucket = self._get_org_bucket(org_id)
        if org_bucket is not None:
            w = await org_bucket.acquire()
            waited += w

        user_bucket = self._get_user_bucket(org_id, user_id)
        if user_bucket is not None:
            w = await user_bucket.acquire()
            waited += w

        if waited > 0:
            RATE_LIMIT_THROTTLED_TOTAL.inc()
            RATE_LIMIT_WAIT_SECONDS.observe(waited)
        return waited


def get_rate_limiter(settings: Settings) -> Optional[AsyncRateLimiter]:
    if not settings.rate_limit_enabled:
        return None
    org_cfg = None
    if settings.org_tokens_per_sec > 0 and settings.org_bucket_size > 0:
        org_cfg = TokenBucketConfig(settings.org_tokens_per_sec, settings.org_bucket_size)
    user_cfg = None
    if settings.user_tokens_per_sec > 0 and settings.user_bucket_size > 0:
        user_cfg = TokenBucketConfig(settings.user_tokens_per_sec, settings.user_bucket_size)
    if org_cfg is None and user_cfg is None:
        return None
    return AsyncRateLimiter(org_cfg, user_cfg)


