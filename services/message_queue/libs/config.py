import os
from typing import Literal, Optional
from pydantic import BaseModel


# Core connection settings
RABBITMQ_URL: str = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/%2F")

# TLS/mTLS configuration for RabbitMQ
RABBITMQ_SSL_CA_PATH: str = os.getenv("RABBITMQ_SSL_CA_PATH", "")
RABBITMQ_SSL_CERT_PATH: str = os.getenv("RABBITMQ_SSL_CERT_PATH", "")
RABBITMQ_SSL_KEY_PATH: str = os.getenv("RABBITMQ_SSL_KEY_PATH", "")
RABBITMQ_SSL_VERIFY: bool = os.getenv("RABBITMQ_SSL_VERIFY", "true").lower() in {"1", "true", "yes"}
RABBITMQ_SSL_CHECK_HOSTNAME: bool = os.getenv("RABBITMQ_SSL_CHECK_HOSTNAME", "true").lower() in {"1", "true", "yes"}

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
    """Typed configuration with sensible defaults for the message queue services.

    Why this exists:
    - Centralize environment configuration and validation across scripts and libs
    - Provide explicit, typed access to commonly used settings

    How to use:
    - Instantiate once per process and pass around, or import where needed
    - Override values via environment variables

    Examples:
    - Configure worker concurrency and prefetch (throughput vs fairness):
      ```bash
      export WORKER_CONCURRENCY=16   # max in-flight messages per worker process
      export WORKER_PREFETCH=32      # AMQP prefetch (QoS) per consumer
      ```
    - Enable TLS for RabbitMQ:
      ```bash
      export RABBITMQ_URL=amqps://user:pass@host:5671/vhost
      export RABBITMQ_SSL_VERIFY=true
      ```
    """
    environment: EnvName = ENVIRONMENT
    rabbitmq_url: str = RABBITMQ_URL
    supabase_url: str = SUPABASE_URL or ""
    supabase_service_role_key: str = SUPABASE_SERVICE_ROLE_KEY or ""
    metrics_port: int = int(os.getenv("METRICS_PORT", "9000"))
    prefetch_count: int = int(os.getenv("WORKER_PREFETCH", "10"))
    worker_concurrency: int = int(os.getenv("WORKER_CONCURRENCY", "10"))
    idempotency_ttl_days: int = int(os.getenv("IDEMPOTENCY_TTL_DAYS", "30"))
    poison_threshold: int = int(os.getenv("POISON_THRESHOLD", "3"))
    # DLQ retention in days for purge job
    dlq_retention_days: int = int(os.getenv("DLQ_RETENTION_DAYS", "90"))

    # Audit batching
    audit_batch_size: int = int(os.getenv("AUDIT_BATCH_SIZE", "100"))
    audit_flush_interval_ms: int = int(os.getenv("AUDIT_FLUSH_INTERVAL_MS", "1000"))
    audit_queue_max: int = int(os.getenv("AUDIT_QUEUE_MAX", "50000"))

    # TLS/mTLS
    rabbitmq_ssl_ca_path: str = RABBITMQ_SSL_CA_PATH
    rabbitmq_ssl_cert_path: str = RABBITMQ_SSL_CERT_PATH
    rabbitmq_ssl_key_path: str = RABBITMQ_SSL_KEY_PATH
    rabbitmq_ssl_verify: bool = RABBITMQ_SSL_VERIFY
    rabbitmq_ssl_check_hostname: bool = RABBITMQ_SSL_CHECK_HOSTNAME

    # Rate limiting (producer-side token bucket)
    rate_limit_enabled: bool = os.getenv("RATE_LIMIT_ENABLED", "false").lower() in {"1", "true", "yes"}
    org_tokens_per_sec: float = float(os.getenv("ORG_TOKENS_PER_SEC", "0"))
    org_bucket_size: int = int(os.getenv("ORG_BUCKET_SIZE", "0"))
    user_tokens_per_sec: float = float(os.getenv("USER_TOKENS_PER_SEC", "0"))
    user_bucket_size: int = int(os.getenv("USER_BUCKET_SIZE", "0"))


