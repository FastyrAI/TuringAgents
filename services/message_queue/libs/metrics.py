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


def start_metrics_server(port: int = 9000) -> None:
    start_http_server(port)


