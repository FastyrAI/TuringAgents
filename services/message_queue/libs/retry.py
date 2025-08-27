"""Retry policy and priority demotion helpers.

This module centralizes retry policy selection and priority demotion decisions
for failed messages. It implements the ADR's Step 1.2 requirements:
 - Error→policy map (no-retry / linear / exponential)
 - Priority demotion P0→P1→P2→P3 on each retry (bounded at P3)

Key entrypoints:
 - ``next_delay_ms``: compute delay for exponential backoff sequences
 - ``demote_priority``: compute next lower priority
 - ``decide_retry``: determine whether to retry, the delay, and next priority

Examples
--------
>>> # Exponential sequence helper
>>> next_delay_ms(0, [1000, 2000, 4000])
1000

>>> # Demote priority (bounded at P3)
>>> demote_priority(1)
2
>>> demote_priority(3)
3

>>> # Decide a retry for a model_call with a generic error
>>> message = {"type": "model_call", "priority": 1, "retry_count": 0}
>>> d = decide_retry(message, Exception("boom"))
>>> (d.should_retry, d.delay_ms, d.next_priority)
(True, 1000, 2)
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Optional

try:  # Optional import; we only use it for error classification
    from pydantic import ValidationError as PydanticValidationError  # type: ignore
except Exception:  # pragma: no cover - pydantic is installed in this project, but safe-guard anyway
    PydanticValidationError = None  # type: ignore[assignment]

from libs.constants import DEFAULT_RETRY_DELAYS_MS


# -------------------------
# Basic helpers
# -------------------------

def next_delay_ms(retry_count: int, delays: List[int] | None = None, jitter: float = 0.0) -> int:
    """Return the next delay in milliseconds for a given retry attempt.

    The ``retry_count`` is zero-based (first retry has ``retry_count == 0``).
    Falls back to the last provided delay if ``retry_count`` exceeds bounds.

    Parameters
    ----------
    retry_count: int
        Zero-based retry attempt counter.
    delays: list[int] | None
        Sequence of backoff delays to use. Defaults to ``DEFAULT_RETRY_DELAYS_MS``.
    jitter: float
        Jitter percentage (0.1 = ±10%) added to the selected delay.

    Returns
    -------
    int
        The computed delay in milliseconds.

    Examples
    --------
    >>> next_delay_ms(2, [100, 200, 400])
    400
    >>> next_delay_ms(5, [100, 200, 400])  # clamped to last
    400
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


def demote_priority(current_priority: int) -> int:
    """Demote logical priority by one, bounded at P3 (value 3).

    Parameters
    ----------
    current_priority: int
        The current logical priority (0..3).

    Returns
    -------
    int
        The next (lower) priority, but never greater than 3.

    Examples
    --------
    >>> demote_priority(0)
    1
    >>> demote_priority(2)
    3
    >>> demote_priority(3)
    3
    """
    return min(max(int(current_priority), 0) + 1, 3)


# -------------------------
# Policy selection
# -------------------------

RetryStrategy = str  # one of: "none", "linear", "exponential"


@dataclass
class RetryPolicy:
    """Retry policy for a message type.

    Attributes
    ----------
    strategy: str
        Policy strategy: "none" | "linear" | "exponential".
    max_retries: int
        Maximum number of retries before dead-lettering.
    base_delay_ms: int
        Base delay used for "linear" strategy (per attempt); ignored for exponential.
    delays: list[int]
        Delay sequence for "exponential" strategy. If empty, falls back to DEFAULT_RETRY_DELAYS_MS.

    Examples
    --------
    >>> RetryPolicy(strategy="exponential", max_retries=3, base_delay_ms=1000, delays=[1000,2000,4000])
    RetryPolicy(strategy='exponential', max_retries=3, base_delay_ms=1000, delays=[1000, 2000, 4000])
    """
    strategy: RetryStrategy
    max_retries: int
    base_delay_ms: int = 1000
    delays: List[int] | None = None


# Defaults per message type (ADR Step 1.2)
DEFAULT_RETRY_POLICIES: dict[str, RetryPolicy] = {
    "model_call": RetryPolicy("exponential", max_retries=3, base_delay_ms=1000, delays=DEFAULT_RETRY_DELAYS_MS),
    "tool_call": RetryPolicy("exponential", max_retries=5, base_delay_ms=1000, delays=DEFAULT_RETRY_DELAYS_MS),
    "memory_save": RetryPolicy("linear", max_retries=10, base_delay_ms=1000, delays=None),
    # Reasonable defaults for other request types
    "agent_message": RetryPolicy("exponential", max_retries=3, base_delay_ms=1000, delays=DEFAULT_RETRY_DELAYS_MS),
    "memory_retrieve": RetryPolicy("linear", max_retries=5, base_delay_ms=500, delays=None),
    "memory_update": RetryPolicy("linear", max_retries=10, base_delay_ms=1000, delays=None),
    "agent_spawn": RetryPolicy("exponential", max_retries=3, base_delay_ms=1000, delays=DEFAULT_RETRY_DELAYS_MS),
    "agent_terminate": RetryPolicy("exponential", max_retries=3, base_delay_ms=1000, delays=DEFAULT_RETRY_DELAYS_MS),
}


def _is_validation_error(exc: Exception) -> bool:
    """Return True if the exception is a validation error (pydantic or similarly named).

    Handles both explicit pydantic ValidationError instances and name-based fallback,
    to keep the detection robust across environments.
    """
    if PydanticValidationError is not None and isinstance(exc, PydanticValidationError):
        return True
    return exc.__class__.__name__ == "ValidationError"


def _is_rate_limit_error(exc: Exception) -> bool:
    """Return True if the exception appears to be a rate limit error.

    We detect by class name to avoid a strict dependency on any specific client library.
    """
    return exc.__class__.__name__ in {"RateLimitError", "TooManyRequests", "HTTP429Error"}


@dataclass
class RetryDecision:
    """Decision computed for a failed message.

    Attributes
    ----------
    should_retry: bool
        Whether the message should be retried.
    delay_ms: int
        Delay before retrying, in milliseconds. Undefined if should_retry is False.
    next_priority: int
        Demoted logical priority to use for the retry.
    next_retry_count: int
        The incremented retry_count value to persist back on the message.
    max_retries: int
        Effective max retries considered when making this decision.
    strategy: str
        The strategy that led to this decision ("none" | "linear" | "exponential").
    error_type: str
        The exception type name used for classification.

    Examples
    --------
    >>> RetryDecision(True, 1000, 2, 1, 3, "exponential", "Exception")
    RetryDecision(should_retry=True, delay_ms=1000, next_priority=2, next_retry_count=1, max_retries=3, strategy='exponential', error_type='Exception')
    """
    should_retry: bool
    delay_ms: int
    next_priority: int
    next_retry_count: int
    max_retries: int
    strategy: RetryStrategy
    error_type: str


def decide_retry(message: dict, exc: Optional[Exception], delays: Optional[List[int]] = None) -> RetryDecision:
    """Decide retry behavior for a failed message.

    This function implements message-type defaults with error-based overrides,
    and priority demotion per retry. It does not mutate the input message.

    Parameters
    ----------
    message: dict
        The failed message payload (expects keys: type, priority, retry_count, max_retries).
    exc: Exception | None
        The exception that caused the failure (used for overrides). If None, generic failure.
    delays: list[int] | None
        Optional exponential backoff delays to prefer (e.g., worker-configured sequence).

    Returns
    -------
    RetryDecision
        The computed decision (whether to retry, with delay, and demoted priority).

    Examples
    --------
    >>> msg = {"type": "model_call", "priority": 1, "retry_count": 0}
    >>> d = decide_retry(msg, Exception("boom"))
    >>> d.should_retry, d.delay_ms, d.next_priority
    (True, 1000, 2)
    """
    msg_type = str(message.get("type", "agent_message"))
    current_priority = int(message.get("priority", 2))
    retry_count = int(message.get("retry_count", 0))
    explicit_max = int(message.get("max_retries", 0))

    # Determine base policy from message type
    policy = DEFAULT_RETRY_POLICIES.get(msg_type)
    if policy is None:
        policy = RetryPolicy("exponential", max_retries=3, base_delay_ms=1000, delays=DEFAULT_RETRY_DELAYS_MS)

    # Effective max retries: explicit > policy > default 3
    max_retries = explicit_max if explicit_max > 0 else (policy.max_retries if policy.max_retries > 0 else 3)

    error_type = exc.__class__.__name__ if exc is not None else "Exception"

    # Error-based overrides
    if exc is not None:
        if _is_validation_error(exc):
            # Never retry validation errors
            return RetryDecision(
                should_retry=False,
                delay_ms=0,
                next_priority=current_priority,
                next_retry_count=retry_count,  # unchanged
                max_retries=max_retries,
                strategy="none",
                error_type=error_type,
            )
        if _is_rate_limit_error(exc):
            # Wait longer for rate limit (60s), but still demote priority
            next_pri = demote_priority(current_priority)
            next_count = retry_count + 1
            return RetryDecision(
                should_retry=(retry_count < max_retries),
                delay_ms=60000,
                next_priority=next_pri,
                next_retry_count=next_count,
                max_retries=max_retries,
                strategy="linear",
                error_type=error_type,
            )

    # No special override: follow policy strategy
    if retry_count >= max_retries:
        return RetryDecision(
            should_retry=False,
            delay_ms=0,
            next_priority=current_priority,
            next_retry_count=retry_count,
            max_retries=max_retries,
            strategy=policy.strategy,
            error_type=error_type,
        )

    if policy.strategy == "linear":
        base = policy.base_delay_ms if policy.base_delay_ms > 0 else 1000
        delay_ms = int(base)
    else:  # exponential (default)
        seq = delays or policy.delays or DEFAULT_RETRY_DELAYS_MS
        delay_ms = next_delay_ms(retry_count, seq)

    next_pri = demote_priority(current_priority)
    next_count = retry_count + 1
    return RetryDecision(
        should_retry=True,
        delay_ms=delay_ms,
        next_priority=next_pri,
        next_retry_count=next_count,
        max_retries=max_retries,
        strategy=policy.strategy,
        error_type=error_type,
    )



