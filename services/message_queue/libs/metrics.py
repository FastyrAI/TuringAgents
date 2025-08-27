"""Prometheus metrics and a tiny HTTP server to expose them.

Call `start_metrics_server(port)` once in a process to expose /metrics.
"""

from __future__ import annotations

from prometheus_client import Counter, Histogram, Gauge, start_http_server


# Core metrics
WORKER_MESSAGE_TOTAL = Counter(
    "worker_message_total", "Total messages processed by the worker", ["status", "type"]
)
WORKER_PROCESS_LATENCY_SECONDS = Histogram(
    "worker_process_latency_seconds", "Time to process a single message", buckets=(0.01, 0.05, 0.1, 0.5, 1, 2, 5)
)
WORKER_RETRY_TOTAL = Counter(
    "worker_retry_total", "Total retries scheduled", ["type"]
)
WORKER_DLQ_TOTAL = Counter(
    "worker_dlq_total", "Total messages sent to DLQ", ["type"]
)
QUEUE_DEPTH = Gauge(
    "queue_depth", "Current queue depth for the org queue", ["org_id"]
)
POISON_QUARANTINED_TOTAL = Counter(
    "poison_quarantined_total", "Total messages quarantined as poison", ["type"]
)

# Publisher metrics
PUBLISH_ATTEMPT_TOTAL = Counter(
    "publish_attempt_total", "Total publish attempts", ["priority", "result"]
)
PUBLISH_FAILED_TOTAL = Counter(
    "publish_failed_total", "Total publish failures", ["reason"]
)

# Rate limiting metrics
RATE_LIMIT_THROTTLED_TOTAL = Counter(
    "rate_limit_throttled_total", "Total times the producer waited for rate limit"
)
RATE_LIMIT_WAIT_SECONDS = Histogram(
    "rate_limit_wait_seconds", "Seconds waited due to token-bucket limiting", buckets=(0.001, 0.01, 0.05, 0.1, 0.5, 1, 2)
)

# Audit batching metrics
AUDIT_EVENT_ENQUEUED_TOTAL = Counter(
    "audit_event_enqueued_total",
    "Total audit events enqueued for batching",
    ["event_type"],
)
AUDIT_EVENTS_DROPPED_TOTAL = Counter(
    "audit_events_dropped_total",
    "Total audit events dropped due to full buffer",
)
AUDIT_BATCH_FLUSH_TOTAL = Counter(
    "audit_batch_flush_total",
    "Total number of audit batch flushes",
    ["reason"],  # size | interval | shutdown
)
AUDIT_BATCH_SIZE = Histogram(
    "audit_batch_size",
    "Number of audit events written in a single batch",
    buckets=(1, 5, 10, 25, 50, 100, 250, 500, 1000),
)
AUDIT_EVENT_WRITE_SECONDS = Histogram(
    "audit_event_write_seconds",
    "Time taken to write an audit batch to the database",
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.25, 0.5, 1, 2),
)


def start_metrics_server(port: int = 9000) -> None:
    start_http_server(port)


