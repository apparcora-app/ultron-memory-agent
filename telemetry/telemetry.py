"""
telemetry.py — Re-export bridge for backward-compatibility.
"""

from telemetry.engine import AuditEvent, TelemetryEngine
from telemetry.tracing import (
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
