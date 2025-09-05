"""
Rate limiting and throttling utilities.
Provides protection against brute force attacks, DDoS, and API abuse.
"""

import time
import asyncio
from typing import Dict, Optional, Tuple, Callable
from collections import defaultdict, deque
import hashlib
import logging
from functools import wraps

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)

# Rate limiting configurations
RATE_LIMITS = {
    # Authentication endpoints
    "auth_login": {"requests": 10, "window": 300, "burst": 10},  # 10 req/5min, burst 10
    "auth_register": {"requests": 3, "window": 300, "burst": 5},  # 3 req/5min, burst 5
    "auth_me": {"requests": 60, "window": 60, "burst": 100},  # 60 req/min, burst 100
    # Composio endpoints
    "composio_action": {
        "requests": 10,
        "window": 60,
        "burst": 15,
    },  # 10 req/min, burst 15
    "composio_auth": {"requests": 5, "window": 300, "burst": 8},  # 5 req/5min, burst 8
    "composio_connections": {
        "requests": 30,
        "window": 60,
        "burst": 50,
    },  # 30 req/min, burst 50
    "composio_providers": {
        "requests": 30,
        "window": 60,
        "burst": 50,
    },  # 30 req/min, burst 50
    # OpenAI API key endpoints
    "openai_key_create": {
        "requests": 3,
        "window": 300,
        "burst": 5,
    },  # 3 req/5min, burst 5
    "openai_key_read": {
        "requests": 30,
        "window": 60,
        "burst": 50,
    },  # 30 req/min, burst 50
    "openai_key_update": {
        "requests": 5,
        "window": 300,
        "burst": 8,
    },  # 5 req/5min, burst 8
    "openai_key_delete": {
        "requests": 2,
        "window": 300,
        "burst": 3,
    },  # 2 req/5min, burst 3
    # Global limits
    "global": {"requests": 100, "window": 60, "burst": 150},  # 100 req/min, burst 150
    "global_user": {
        "requests": 200,
        "window": 60,
        "burst": 300,
    },  # 200 req/min per user, burst 300
}

# Blocked IPs and users (in production, this would be in a database or Redis)
BLOCKED_IPS = set()
BLOCKED_USERS = set()

# Temporary ban durations (in seconds)
BAN_DURATIONS = {
    "short": 300,  # 5 minutes
    "medium": 1800,  # 30 minutes
    "long": 3600,  # 1 hour
    "extended": 86400,  # 24 hours
}


class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded."""

    def __init__(self, retry_after: int, limit_type: str = ""):
        self.retry_after = retry_after
        self.limit_type = limit_type
        super().__init__(f"Rate limit exceeded. Try again in {retry_after} seconds.")


class TokenBucket:
    """Token bucket algorithm implementation for rate limiting."""

    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.tokens = capacity
        self.refill_rate = refill_rate
        self.last_refill = time.time()

    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens from the bucket.

        Args:
            tokens: Number of tokens to consume

        Returns:
            True if tokens were consumed, False if not enough tokens
        """
        now = time.time()

        # Refill tokens based on time passed
        time_passed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + time_passed * self.refill_rate)
        self.last_refill = now

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True

        return False

    def time_until_token(self) -> float:
        """Calculate time until next token is available."""
        if self.tokens >= 1:
            return 0
        return (1 - self.tokens) / self.refill_rate


class SlidingWindowCounter:
    """Sliding window counter for rate limiting."""

    def __init__(self, window_size: int):
        self.window_size = window_size
        self.requests = deque()

    def add_request(self) -> int:
        """
        Add a request to the window and return current count.

        Returns:
            Current number of requests in window
        """
        now = time.time()

        # Remove old requests outside the window
        while self.requests and self.requests[0] <= now - self.window_size:
            self.requests.popleft()

        # Add current request
        self.requests.append(now)

        return len(self.requests)

    def get_count(self) -> int:
        """Get current number of requests in window."""
        now = time.time()

        # Remove old requests
        while self.requests and self.requests[0] <= now - self.window_size:
            self.requests.popleft()

        return len(self.requests)

    def time_until_oldest_expires(self) -> float:
        """Time until the oldest request expires."""
        if not self.requests:
            return 0

        now = time.time()
        oldest_request = self.requests[0]
        expiry_time = oldest_request + self.window_size

        return max(0, expiry_time - now)


class InMemoryRateLimiter:
    """In-memory rate limiter using sliding window counters."""

    def __init__(self):
        self.counters: Dict[str, SlidingWindowCounter] = defaultdict(lambda: None)
        self.buckets: Dict[str, TokenBucket] = defaultdict(lambda: None)
        self.blocked_until: Dict[str, float] = {}
        self.violation_counts: Dict[str, int] = defaultdict(int)

    def is_blocked(self, key: str) -> Tuple[bool, float]:
        """
        Check if a key is temporarily blocked.

        Args:
            key: Rate limit key to check

        Returns:
            Tuple of (is_blocked, time_remaining)
        """
        if key in self.blocked_until:
            remaining = self.blocked_until[key] - time.time()
            if remaining > 0:
                return True, remaining
            else:
                # Block expired, remove it
                del self.blocked_until[key]

        return False, 0

    def block_key(self, key: str, duration: int):
        """Block a key for a specified duration."""
        self.blocked_until[key] = time.time() + duration
        self.violation_counts[key] += 1
        logger.warning(
            f"Blocked key {key} for {duration} seconds (violation #{self.violation_counts[key]})"
        )

    def check_rate_limit(
        self, key: str, limit_config: Dict[str, int], use_token_bucket: bool = False
    ) -> Tuple[bool, int]:
        """
        Check if request is within rate limits.

        Args:
            key: Unique key for rate limiting (IP, user_id, endpoint, etc.)
            limit_config: Configuration with 'requests', 'window', 'burst'
            use_token_bucket: Whether to use token bucket algorithm

        Returns:
            Tuple of (is_allowed, retry_after_seconds)
        """
        # Check if key is blocked
        is_blocked, time_remaining = self.is_blocked(key)
        if is_blocked:
            return False, int(time_remaining) + 1

        if use_token_bucket:
            return self._check_token_bucket(key, limit_config)
        else:
            return self._check_sliding_window(key, limit_config)

    def _check_token_bucket(
        self, key: str, limit_config: Dict[str, int]
    ) -> Tuple[bool, int]:
        """Check rate limit using token bucket algorithm."""
        requests_per_second = limit_config["requests"] / limit_config["window"]
        capacity = limit_config.get("burst", limit_config["requests"])

        if key not in self.buckets or self.buckets[key] is None:
            self.buckets[key] = TokenBucket(capacity, requests_per_second)

        bucket = self.buckets[key]

        if bucket.consume():
            return True, 0
        else:
            retry_after = int(bucket.time_until_token()) + 1

            # Apply progressive blocking for repeated violations
            self._apply_progressive_blocking(key, retry_after)

            return False, retry_after

    def _check_sliding_window(
        self, key: str, limit_config: Dict[str, int]
    ) -> Tuple[bool, int]:
        """Check rate limit using sliding window algorithm."""
        window_size = limit_config["window"]
        max_requests = limit_config["requests"]

        if key not in self.counters or self.counters[key] is None:
            self.counters[key] = SlidingWindowCounter(window_size)

        counter = self.counters[key]
        current_count = counter.add_request()

        if current_count <= max_requests:
            return True, 0
        else:
            retry_after = int(counter.time_until_oldest_expires()) + 1

            # Apply progressive blocking for repeated violations
            self._apply_progressive_blocking(key, retry_after)

            return False, retry_after

    def _apply_progressive_blocking(self, key: str, base_retry_after: int):
        """Apply progressive blocking for repeated violations."""
        violations = self.violation_counts[key]

        # Progressive blocking based on violation count
        if violations >= 10:
            self.block_key(key, BAN_DURATIONS["extended"])  # 24 hours
        elif violations >= 5:
            self.block_key(key, BAN_DURATIONS["long"])  # 1 hour
        elif violations >= 3:
            self.block_key(key, BAN_DURATIONS["medium"])  # 30 minutes
        elif violations >= 1:
            self.block_key(key, BAN_DURATIONS["short"])  # 5 minutes

    def reset_counter(self, key: str):
        """Reset rate limit counter for a key."""
        if key in self.counters:
            del self.counters[key]
        if key in self.buckets:
            del self.buckets[key]
        if key in self.violation_counts:
            del self.violation_counts[key]

    def get_stats(self, key: str) -> Dict[str, any]:
        """Get rate limiting stats for a key."""
        stats = {
            "key": key,
            "violations": self.violation_counts.get(key, 0),
            "is_blocked": False,
            "block_expires": None,
            "current_requests": 0,
        }

        # Check if blocked
        is_blocked, time_remaining = self.is_blocked(key)
        if is_blocked:
            stats["is_blocked"] = True
            stats["block_expires"] = time.time() + time_remaining

        # Get current request count
        if key in self.counters and self.counters[key] is not None:
            stats["current_requests"] = self.counters[key].get_count()

        return stats


# Global rate limiter instance
rate_limiter = InMemoryRateLimiter()


def get_client_identifier(request: Request) -> str:
    """Get unique identifier for client (IP address)."""
    # Try to get real IP from headers (behind proxy)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fallback to direct client IP
    return request.client.host if request.client else "unknown"


def get_user_identifier(request: Request) -> Optional[str]:
    """Get user identifier from JWT token if available."""
    try:
        from ..core.security import extract_token_from_header, get_current_user_id

        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return None

        token = extract_token_from_header(auth_header)
        if not token:
            return None

        user_id = get_current_user_id(token)
        return str(user_id) if user_id else None

    except Exception:
        return None


def create_rate_limit_key(identifier: str, limit_type: str) -> str:
    """Create a unique rate limit key."""
    # Hash the identifier for privacy and consistent length
    hashed_id = hashlib.sha256(identifier.encode()).hexdigest()[:16]
    return f"{limit_type}:{hashed_id}"


async def check_rate_limits(request: Request, limit_types: list[str]) -> None:
    """
    Check multiple rate limits for a request.

    Args:
        request: FastAPI request object
        limit_types: List of rate limit types to check

    Raises:
        HTTPException: If any rate limit is exceeded
    """
    client_ip = get_client_identifier(request)
    user_id = get_user_identifier(request)

    # Check if IP is blocked
    if client_ip in BLOCKED_IPS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your IP address has been blocked",
        )

    # Check if user is blocked
    if user_id and user_id in BLOCKED_USERS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been blocked",
        )

    # Check each rate limit type
    for limit_type in limit_types:
        if limit_type not in RATE_LIMITS:
            logger.warning(f"Unknown rate limit type: {limit_type}")
            continue

        limit_config = RATE_LIMITS[limit_type]

        # Check IP-based limit
        ip_key = create_rate_limit_key(client_ip, f"{limit_type}_ip")
        is_allowed, retry_after = rate_limiter.check_rate_limit(ip_key, limit_config)

        if not is_allowed:
            logger.warning(f"Rate limit exceeded for IP {client_ip} on {limit_type}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded for {limit_type}. Try again in {retry_after} seconds.",
                headers={"Retry-After": str(retry_after)},
            )

        # Check user-based limit if user is authenticated
        if user_id:
            user_key = create_rate_limit_key(user_id, f"{limit_type}_user")
            is_allowed, retry_after = rate_limiter.check_rate_limit(
                user_key, limit_config
            )

            if not is_allowed:
                logger.warning(
                    f"Rate limit exceeded for user {user_id} on {limit_type}"
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded for {limit_type}. Try again in {retry_after} seconds.",
                    headers={"Retry-After": str(retry_after)},
                )


def rate_limit(limit_types: list[str]):
    """
    Decorator for rate limiting endpoints.

    Args:
        limit_types: List of rate limit types to apply
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Find the request object in arguments
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break

            if not request:
                # If no request found in args, check kwargs
                request = kwargs.get("request")

            if request:
                await check_rate_limits(request, limit_types)

            return (
                await func(*args, **kwargs)
                if asyncio.iscoroutinefunction(func)
                else func(*args, **kwargs)
            )

        return wrapper

    return decorator


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Global rate limiting middleware."""

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request with global rate limiting."""

        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/health/db", "/health/full"]:
            return await call_next(request)

        try:
            # Apply global rate limits
            await check_rate_limits(request, ["global"])

            # If user is authenticated, apply user-specific global limits
            user_id = get_user_identifier(request)
            if user_id:
                await check_rate_limits(request, ["global_user"])

        except HTTPException as e:
            # Return rate limit response
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=e.status_code,
                content={
                    "success": False,
                    "message": e.detail,
                    "error_type": "rate_limit_exceeded",
                },
                headers=e.headers,
            )

        # Continue with request
        response = await call_next(request)

        # Add rate limit headers
        client_ip = get_client_identifier(request)
        ip_key = create_rate_limit_key(client_ip, "global_ip")
        stats = rate_limiter.get_stats(ip_key)

        response.headers["X-RateLimit-Limit"] = str(RATE_LIMITS["global"]["requests"])
        response.headers["X-RateLimit-Remaining"] = str(
            max(0, RATE_LIMITS["global"]["requests"] - stats["current_requests"])
        )
        response.headers["X-RateLimit-Reset"] = str(
            int(time.time() + RATE_LIMITS["global"]["window"])
        )

        return response


# Utility functions for managing blocked IPs and users
def block_ip(ip_address: str, reason: str = ""):
    """Block an IP address."""
    BLOCKED_IPS.add(ip_address)
    logger.warning(f"Blocked IP address: {ip_address}. Reason: {reason}")


def unblock_ip(ip_address: str):
    """Unblock an IP address."""
    BLOCKED_IPS.discard(ip_address)
    logger.info(f"Unblocked IP address: {ip_address}")


def block_user(user_id: str, reason: str = ""):
    """Block a user."""
    BLOCKED_USERS.add(user_id)
    logger.warning(f"Blocked user: {user_id}. Reason: {reason}")


def unblock_user(user_id: str):
    """Unblock a user."""
    BLOCKED_USERS.discard(user_id)
    logger.info(f"Unblocked user: {user_id}")


def get_rate_limit_status(identifier: str, limit_type: str) -> Dict[str, any]:
    """Get rate limit status for debugging."""
    key = create_rate_limit_key(identifier, limit_type)
    return rate_limiter.get_stats(key)


def reset_rate_limits(identifier: str, limit_type: str = None):
    """Reset rate limits for an identifier."""
    if limit_type:
        key = create_rate_limit_key(identifier, limit_type)
        rate_limiter.reset_counter(key)
    else:
        # Reset all rate limits for this identifier
        for lt in RATE_LIMITS.keys():
            key = create_rate_limit_key(identifier, lt)
            rate_limiter.reset_counter(key)
