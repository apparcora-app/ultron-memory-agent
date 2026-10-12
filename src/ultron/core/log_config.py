"""
core/log_config.py — Structured JSON Logging for Ultron.

Provides:
  - get_logger(name)       : returns a logger scoped to __name__ with JSON formatter
  - correlation_id_ctx     : contextvars.ContextVar for per-turn correlation IDs
  - new_correlation_id()   : generate a fresh UUID4 short correlation ID
  - bind_correlation_id(cid): context manager that sets the ID for the duration of a call
  - UltronJsonFormatter    : pythonjsonlogger formatter that auto-injects correlation_id
"""
from __future__ import annotations

import logging
import sys
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar

# ── Correlation-ID context variable ──────────────────────────────────────────
#  A ContextVar is the safe, async-compatible way to store per-task state.
#  It is automatically inherited by threads spawned inside an async task,
#  and survives asyncio task switches without cross-contamination.
correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="no-cid")


def new_correlation_id() -> str:
    """Generate a short UUID4 suitable for log correlation."""
    return uuid.uuid4().hex[:12]


@contextmanager
def bind_correlation_id(cid: str | None = None) -> Generator[str, None, None]:
    """
    Context manager that sets a correlation ID for the current execution context.
    Usage:
        with bind_correlation_id() as cid:
            logger.info("Starting turn", extra={"cid": cid})
    """
    cid = cid or new_correlation_id()
    token = correlation_id_ctx.set(cid)
    try:
        yield cid
    finally:
        correlation_id_ctx.reset(token)


# ── JSON Formatter ────────────────────────────────────────────────────────────
try:
    from pythonjsonlogger import jsonlogger  # python-json-logger >= 2.x

    class UltronJsonFormatter(jsonlogger.JsonFormatter):
        """Extends JsonFormatter to always include the active correlation_id."""

        def add_fields(self, log_record: dict, record: logging.LogRecord, message_dict: dict) -> None:
            super().add_fields(log_record, record, message_dict)
            log_record["correlation_id"] = correlation_id_ctx.get()
            log_record["logger"] = record.name
            # Remove verbose keys that clutter JSON output
            log_record.pop("color_message", None)

    _FORMATTER: logging.Formatter = UltronJsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    _USING_JSON = True

except ImportError:  # pragma: no cover — fallback for environments without the library
    _USING_JSON = False

    class _PlainFormatter(logging.Formatter):  # type: ignore[no-redef]
        def format(self, record: logging.LogRecord) -> str:
            cid = correlation_id_ctx.get()
            record.correlation_id = cid
            return super().format(record)

    _FORMATTER = _PlainFormatter(
        fmt="%(asctime)s [%(levelname)s] [%(correlation_id)s] %(name)s — %(message)s"
    )


# ── Handler & root configuration ─────────────────────────────────────────────
def _build_handler() -> logging.Handler:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_FORMATTER)
    return handler


# Configure the "ultron" namespace logger once at import time.
_ultron_root = logging.getLogger("ultron")
if not _ultron_root.handlers:
    _ultron_root.addHandler(_build_handler())
    _ultron_root.setLevel(logging.DEBUG)
    _ultron_root.propagate = False  # Don't double-log to the root logger


def get_logger(name: str) -> logging.Logger:
    """
    Return a child logger under the 'ultron' namespace.

    Convention:
        logger = get_logger(__name__)

    All loggers created this way automatically inherit:
      - The JSON formatter
      - The correlation_id injection
      - The 'ultron' handler
    """
    # Normalize: strip leading package prefixes for brevity
    short = name.replace("ultron_memory_agent.", "").replace("ultron-memory-agent.", "")
    return logging.getLogger(f"ultron.{short}")
