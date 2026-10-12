"""
telemetry package — Observability, Prometheus Exporter, and Distributed Tracing.

Exports:
  1. TelemetryEngine, AuditEvent
  2. Tracer, Span, default_tracer, get_current_trace_id, get_current_span_id
"""

from ultron.telemetry.engine import AuditEvent, TelemetryEngine
from ultron.telemetry.tracing import (
    Span,
    Tracer,
    default_tracer,
    get_current_span_id,
    get_current_trace_id,
)

__all__ = [
    "AuditEvent",
    "TelemetryEngine",
    "Span",
    "Tracer",
    "default_tracer",
    "get_current_span_id",
    "get_current_trace_id",
]
