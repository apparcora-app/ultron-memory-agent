"""
telemetry/tracing.py — Distributed Tracing & Span Lifecycle.

Provides:
  1. Async-safe trace context propagation using Python's `contextvars`.
  2. Preserves trace_id, span_id, and parent_span_id across LangGraph node boundaries,
     parallel tool executions, and subtask delegations.
  3. Structured span telemetry: timestamps, duration_ms, token counts, status (OK/ERROR),
     attributes, and error serialization.
"""

from __future__ import annotations

import contextvars
import time
import uuid
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# ── Context Variables for Distributed Tracing ─────────────────────────────────

_current_trace_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("current_trace_id", default=None)
_current_span_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("current_span_id", default=None)


def get_current_trace_id() -> str:
    """Returns the active trace_id or generates a new root trace ID if none exists."""
    tid = _current_trace_id.get()
    if tid is None:
        tid = f"tr_{uuid.uuid4().hex[:12]}"
        _current_trace_id.set(tid)
    return tid


def get_current_span_id() -> str | None:
    """Returns the active span_id in the current execution context."""
    return _current_span_id.get()


# ── Span Data Model ───────────────────────────────────────────────────────────

class Span(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    span_id: str
    trace_id: str
    parent_span_id: str | None = None
    name: str
    component: str = "core"
    start_time: float = Field(default_factory=time.time)
    end_time: float | None = None
    duration_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    status: Literal["OK", "ERROR"] = "OK"
    error_message: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)

    def finish(self, status: Literal["OK", "ERROR"] = "OK", error: Exception | str | None = None) -> None:
        self.end_time = time.time()
        self.duration_ms = round((self.end_time - self.start_time) * 1000.0, 2)
        self.status = status
        if error is not None:
            self.error_message = str(error)
            self.status = "ERROR"

    def set_tokens(self, input_tokens: int = 0, output_tokens: int = 0) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value


# ── Tracer Engine ─────────────────────────────────────────────────────────────

class Tracer:
    """
    Distributed tracing coordinator managing context propagation,
    span hierarchy trees, and span storage.
    """

    def __init__(self) -> None:
        self._spans: list[Span] = []

    def clear(self) -> None:
        self._spans.clear()

    def get_spans(self, trace_id: str | None = None) -> list[Span]:
        """Returns all completed spans, optionally filtered by trace_id."""
        if trace_id is not None:
            return [s for s in self._spans if s.trace_id == trace_id]
        return list(self._spans)

    @contextmanager
    def trace_context(self, trace_id: str | None = None) -> Iterator[str]:
        """Explicitly sets or preserves a trace_id for the duration of a block."""
        tid = trace_id or f"tr_{uuid.uuid4().hex[:12]}"
        token = _current_trace_id.set(tid)
        try:
            yield tid
        finally:
            _current_trace_id.reset(token)

    @contextmanager
    def span(
        self,
        name: str,
        component: str = "core",
        attributes: dict[str, Any] | None = None,
    ) -> Iterator[Span]:
        """
        Synchronous context manager creating a child span under the current trace
        and parent span context.
        """
        trace_id = get_current_trace_id()
        parent_id = get_current_span_id()
        span_id = f"sp_{uuid.uuid4().hex[:8]}"

        span_obj = Span(
            span_id=span_id,
            trace_id=trace_id,
            parent_span_id=parent_id,
            name=name,
            component=component,
            attributes=attributes or {},
        )

        span_token = _current_span_id.set(span_id)
        try:
            yield span_obj
            span_obj.finish("OK")
        except Exception as exc:
            span_obj.finish("ERROR", error=exc)
            raise
        finally:
            _current_span_id.reset(span_token)
            self._spans.append(span_obj)

    @asynccontextmanager
    async def async_span(
        self,
        name: str,
        component: str = "core",
        attributes: dict[str, Any] | None = None,
    ) -> AsyncIterator[Span]:
        """
        Asynchronous context manager creating a child span under the current trace
        and parent span context. Safe across asyncio tasks and coroutines.
        """
        trace_id = get_current_trace_id()
        parent_id = get_current_span_id()
        span_id = f"sp_{uuid.uuid4().hex[:8]}"

        span_obj = Span(
            span_id=span_id,
            trace_id=trace_id,
            parent_span_id=parent_id,
            name=name,
            component=component,
            attributes=attributes or {},
        )

        span_token = _current_span_id.set(span_id)
        try:
            yield span_obj
            span_obj.finish("OK")
        except Exception as exc:
            span_obj.finish("ERROR", error=exc)
            raise
        finally:
            _current_span_id.reset(span_token)
            self._spans.append(span_obj)


# Global default tracer instance
default_tracer = Tracer()
