from prometheus_client import Counter, Histogram, Gauge, start_http_server


# Ingestion metrics
INGEST_TOTAL = Counter(
    "ctx_v2_ingest_total", "Total items ingested into Neo4j (v2)", ["type", "result"]
)
INGEST_LATENCY_SECONDS = Histogram(
    "ctx_v2_ingest_latency_seconds",
    "Latency of ingestion operations (v2)",
    buckets=(0.01, 0.05, 0.1, 0.5, 1, 2, 5),
)

# Retrieval metrics
RETRIEVE_TOTAL = Counter(
    "ctx_v2_retrieve_total", "Total retrieval queries (v2)", ["strategy"]
)
RETRIEVE_LATENCY_SECONDS = Histogram(
    "ctx_v2_retrieve_latency_seconds",
    "Latency of retrieval queries (v2)",
    buckets=(0.01, 0.05, 0.1, 0.5, 1, 2, 5),
)

# Summarization metrics
SUMMARIZE_TOTAL = Counter(
    "ctx_v2_summarize_total", "Total summarizations (v2)", ["mode"]
)
SUMMARIZE_LATENCY_SECONDS = Histogram(
    "ctx_v2_summarize_latency_seconds",
    "Latency of summarization (v2)",
    ["mode"],
    buckets=(0.05, 0.2, 0.5, 1, 2, 5, 10),
)

# Router decisions
ROUTER_DECISION_TOTAL = Counter(
    "ctx_v2_router_decision_total", "LLM provider decisions (v2)", ["provider", "reason"]
)

# Faithfulness and verification
MUST_INCLUDE_COVERAGE = Histogram(
    "ctx_v2_must_include_coverage",
    "Distribution of must-include coverage (0..1)",
    buckets=(0.5, 0.7, 0.8, 0.9, 0.95, 0.98, 1.0),
)
NUMERIC_MISMATCH_RATE = Histogram(
    "ctx_v2_numeric_mismatch_rate",
    "Distribution of numeric mismatch rate (0..1)",
    buckets=(0.0, 0.001, 0.005, 0.01, 0.02, 0.05, 0.1),
)

# Graph & conflicts
GRAPH_NODES_GAUGE = Gauge("ctx_v2_graph_nodes", "Approximate node count (sampled)")
CONFLICT_TOTAL = Counter("ctx_v2_conflict_total", "Total conflict events", ["type"])

# Health
HEALTH_GAUGE = Gauge("ctx_v2_health", "Service health status (1=ok,0=down)")


def start_metrics_server(port: int = 9101) -> None:
    start_http_server(port)
