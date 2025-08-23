"""OpenTelemetry tracing helpers for producer/worker/coordinator.

By default, spans are exported to the console. If the environment variable
`OTEL_EXPORTER_OTLP_ENDPOINT` is set and the OTLP exporter is available, spans
are exported to that endpoint instead.
"""

from __future__ import annotations

from typing import Dict, Mapping, Any

from opentelemetry import trace, context  # type: ignore
from opentelemetry.sdk.resources import Resource  # type: ignore
from opentelemetry.sdk.trace import TracerProvider  # type: ignore
from opentelemetry.sdk.trace.export import SimpleSpanProcessor  # type: ignore
from opentelemetry.trace import Tracer  # type: ignore
from opentelemetry.propagate import get_global_textmap, set_global_textmap, inject  # type: ignore
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator  # type: ignore


def start_tracing(service_name: str = "turing-agents") -> Tracer:
    """Initialize a TracerProvider with console or OTLP exporter."""
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    from opentelemetry.sdk.trace.export import ConsoleSpanExporter  # type: ignore
    exporter = ConsoleSpanExporter()

    processor = SimpleSpanProcessor(exporter)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    # Ensure W3C tracecontext propagator is used for headers
    set_global_textmap(TraceContextTextMapPropagator())

    return trace.get_tracer(service_name)


def get_tracer(service_name: str = "turing-agents") -> Tracer:
    return trace.get_tracer(service_name)


def inject_headers(headers: Dict[str, str] | None = None) -> Dict[str, str]:
    """Inject current context into AMQP headers (dict[str, str])."""
    carrier: Dict[str, str] = {} if headers is None else dict(headers)
    inject(carrier)
    return carrier


def extract_context_from_headers(headers: Mapping[str, Any] | None):
    """Return a context object extracted from AMQP headers.

    Converts header values to strings to satisfy the propagator requirements.
    """
    carrier: Dict[str, str] = {}
    if headers:
        for k, v in headers.items():
            try:
                carrier[str(k)] = v if isinstance(v, str) else str(v)
            except Exception:
                continue
    propagator = get_global_textmap()
    return propagator.extract(carrier)


