import os
from typing import Literal, Optional
from pydantic import BaseModel


# Core connection settings
RABBITMQ_URL: str = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/%2F")

# Supabase configuration (server-side usage should prefer service role key)
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")


# Priority mapping: logical (0-3) -> AMQP (0-9)
_LOGICAL_TO_AMQP = {0: 9, 1: 6, 2: 3, 3: 0}


def map_logical_priority_to_amqp(logical_priority: int) -> int:
    """Map logical priority P0..P3 to AMQP priority range 0..9.

    P0 -> 9, P1 -> 6, P2 -> 3, P3 -> 0
    Defaults to P2 (3) if out-of-range.
    """
    return _LOGICAL_TO_AMQP.get(int(logical_priority), 3)


def parse_priority(value: str | int) -> int:
    """Parse user-provided priority into logical 0..3 (P0..P3)."""
    if isinstance(value, int):
        return min(max(value, 0), 3)
    v = str(value).strip().upper()
    if v.startswith("P") and v[1:].isdigit():
        return min(max(int(v[1:]), 0), 3)
    if v.isdigit():
        return min(max(int(v), 0), 3)
    return 2  # default P2


EnvName = Literal["development", "staging", "production"]
ENVIRONMENT: EnvName = os.getenv("ENVIRONMENT", "development").lower()  # type: ignore[assignment]


def is_prod() -> bool:
    return ENVIRONMENT == "production"


def is_supabase_configured() -> bool:
    return bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)


_supabase_client: Optional[object] = None


def get_supabase_client():
    """Lazily create and cache a Supabase client if configured, else return None."""
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client
    if not is_supabase_configured():
        return None
    # Import lazily to avoid hard dependency if not configured
    from supabase import create_client  # type: ignore

    _supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    return _supabase_client


class Settings(BaseModel):
    """Typed configuration with sensible defaults.

    Use this for centralized env validation when services start.
    """
    environment: EnvName = ENVIRONMENT
    rabbitmq_url: str = RABBITMQ_URL
    supabase_url: str = SUPABASE_URL or ""
    supabase_service_role_key: str = SUPABASE_SERVICE_ROLE_KEY or ""
    metrics_port: int = int(os.getenv("METRICS_PORT", "9000"))
    prefetch_count: int = int(os.getenv("WORKER_PREFETCH", "10"))
    idempotency_ttl_days: int = int(os.getenv("IDEMPOTENCY_TTL_DAYS", "30"))
    poison_threshold: int = int(os.getenv("POISON_THRESHOLD", "3"))


