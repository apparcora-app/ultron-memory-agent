"""
resilience/dlq.py — Dead Letter Queue (DLQ) & Persistent Error Telemetry.

Provides:
  1. Persistent SQLite storage for unrecoverable agent, model, and tool failures.
  2. Captured metadata: dlq_id, trace_id, timestamp, failed_service, node_name,
     input_payload, retry_attempts, circuit_state, error_type, error_message, full_stack_trace.
  3. Queryable inspection API and offline replay helpers (reconstruct_failed_task, requeue, purge).
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import traceback
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ultron.core.log_config import get_logger
from ultron.telemetry.tracing import get_current_trace_id

try:
    from ultron.security.sanitizer import sanitize_text
except ImportError:
    def sanitize_text(t: str) -> str:
        return t


class DeadLetterRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    dlq_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    failed_service: str
    node_name: str
    input_payload: dict[str, Any] | str | None = None
    retry_attempts: int = 0
    circuit_state: str = "UNKNOWN"
    error_type: str
    error_message: str
    full_stack_trace: str = ""
    status: str = "PENDING"  # PENDING, REQUEUED, REPLAYED, DISCARDED

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


class DeadLetterQueue:
    """
    Persistent Dead Letter Queue backed by SQLite for offline triage, auditing, and replay.
    """

    def __init__(self, db_path: str = "./data/dead_letters.db") -> None:
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    @contextmanager
    def _conn_ctx(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._lock:
            with self._conn_ctx() as conn:
                with conn:
                    conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS dead_letter_traces (
                            dlq_id TEXT PRIMARY KEY,
                            trace_id TEXT,
                            timestamp TEXT,
                            failed_service TEXT,
                            node_name TEXT,
                            input_payload TEXT,
                            retry_attempts INTEGER,
                            circuit_state TEXT,
                            error_type TEXT,
                            error_message TEXT,
                            full_stack_trace TEXT,
                            status TEXT DEFAULT 'PENDING'
                        )
                        """
                    )
                    conn.execute(
                        "CREATE INDEX IF NOT EXISTS idx_dlq_trace_id ON dead_letter_traces(trace_id)"
                    )
                    conn.execute(
                        "CREATE INDEX IF NOT EXISTS idx_dlq_status ON dead_letter_traces(status)"
                    )

    def record_dead_letter(
        self,
        failed_service: str,
        node_name: str,
        error: Exception | None = None,
        error_type: str | None = None,
        error_message: str | None = None,
        full_stack_trace: str | None = None,
        input_payload: dict[str, Any] | str | None = None,
        trace_id: str | None = None,
        retry_attempts: int = 0,
        circuit_state: str = "UNKNOWN",
        dlq_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DeadLetterRecord:
        """
        Captures an unrecoverable failure snapshot and persists it into the DLQ database.
        """
        active_trace_id = trace_id or get_current_trace_id()
        record_id = dlq_id or str(uuid.uuid4())

        err_type = error_type or (type(error).__name__ if error else "UnknownError")
        raw_err_msg = error_message or (str(error) if error else "Unspecified unrecoverable failure")
        raw_stack_trace = full_stack_trace or (traceback.format_exc() if error else "")

        err_msg = sanitize_text(raw_err_msg)
        stack_trace = sanitize_text(raw_stack_trace)

        payload = input_payload if input_payload is not None else metadata
        serialized_payload: str | None = None
        if payload is not None:
            if isinstance(payload, str):
                serialized_payload = sanitize_text(payload)
            else:
                try:
                    serialized_payload = sanitize_text(json.dumps(payload, default=str))
                except Exception:
                    serialized_payload = sanitize_text(str(payload))

        record = DeadLetterRecord(
            dlq_id=record_id,
            trace_id=active_trace_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            failed_service=failed_service,
            node_name=node_name,
            input_payload=serialized_payload,
            retry_attempts=retry_attempts,
            circuit_state=circuit_state,
            error_type=err_type,
            error_message=err_msg,
            full_stack_trace=stack_trace,
            status="PENDING",
        )

        with self._lock:
            with self._conn_ctx() as conn:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO dead_letter_traces (
                            dlq_id, trace_id, timestamp, failed_service, node_name,
                            input_payload, retry_attempts, circuit_state,
                            error_type, error_message, full_stack_trace, status
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            record.dlq_id,
                            record.trace_id,
                            record.timestamp,
                            record.failed_service,
                            record.node_name,
                            serialized_payload,
                            record.retry_attempts,
                            record.circuit_state,
                            record.error_type,
                            record.error_message,
                            record.full_stack_trace,
                            record.status,
                        ),
                    )

        return record

    def list_dead_letters(
        self,
        limit: int = 50,
        status: str | None = None,
        trace_id: str | None = None,
    ) -> list[DeadLetterRecord]:
        """Queries dead letter records with optional status and trace_id filtering."""
        query = "SELECT * FROM dead_letter_traces WHERE 1=1"
        params: list[Any] = []

        if status:
            query += " AND status = ?"
            params.append(status)
        if trace_id:
            query += " AND trace_id = ?"
            params.append(trace_id)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with self._lock:
            with self._conn_ctx() as conn:
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()

        return [
            DeadLetterRecord(
                dlq_id=r["dlq_id"],
                trace_id=r["trace_id"],
                timestamp=r["timestamp"],
                failed_service=r["failed_service"],
                node_name=r["node_name"],
                input_payload=r["input_payload"],
                retry_attempts=r["retry_attempts"],
                circuit_state=r["circuit_state"],
                error_type=r["error_type"],
                error_message=r["error_message"],
                full_stack_trace=r["full_stack_trace"],
                status=r["status"],
            )
            for r in rows
        ]

    def get_dead_letter(self, dlq_id: str) -> DeadLetterRecord | None:
        """Fetches a single dead letter record by its unique dlq_id."""
        with self._lock:
            with self._conn_ctx() as conn:
                cursor = conn.execute(
                    "SELECT * FROM dead_letter_traces WHERE dlq_id = ?",
                    (dlq_id,),
                )
                row = cursor.fetchone()

        if not row:
            return None

        return DeadLetterRecord(
            dlq_id=row["dlq_id"],
            trace_id=row["trace_id"],
            timestamp=row["timestamp"],
            failed_service=row["failed_service"],
            node_name=row["node_name"],
            input_payload=row["input_payload"],
            retry_attempts=row["retry_attempts"],
            circuit_state=row["circuit_state"],
            error_type=row["error_type"],
            error_message=row["error_message"],
            full_stack_trace=row["full_stack_trace"],
            status=row["status"],
        )

    def update_status(self, dlq_id: str, new_status: str) -> bool:
        """Updates the resolution status of a dead letter record."""
        with self._lock:
            with self._conn_ctx() as conn:
                with conn:
                    cursor = conn.execute(
                        "UPDATE dead_letter_traces SET status = ? WHERE dlq_id = ?",
                        (new_status, dlq_id),
                    )
                    return cursor.rowcount > 0

    def reconstruct_failed_task(self, dlq_id: str) -> dict[str, Any]:
        """
        Decodes and reconstructs the failed task context for offline replay or testing.
        """
        record = self.get_dead_letter(dlq_id)
        if not record:
            raise ValueError(f"DLQ record '{dlq_id}' not found.")

        parsed_payload: Any = record.input_payload
        if isinstance(record.input_payload, str):
            try:
                parsed_payload = json.loads(record.input_payload)
            except Exception:
                parsed_payload = record.input_payload

        return {
            "dlq_id": record.dlq_id,
            "trace_id": record.trace_id,
            "timestamp": record.timestamp,
            "failed_service": record.failed_service,
            "node_name": record.node_name,
            "input_payload": parsed_payload,
            "retry_attempts": record.retry_attempts,
            "circuit_state": record.circuit_state,
            "error_type": record.error_type,
            "error_message": record.error_message,
            "can_reexecute": True,
        }

    def requeue(self, dlq_id: str) -> bool:
        """Marks a dead letter record as REQUEUED for retry."""
        return self.update_status(dlq_id, "REQUEUED")

    @property
    def queue_depth(self) -> int:
        """Returns the count of pending dead letters currently awaiting triage."""
        with self._lock:
            with self._conn_ctx() as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM dead_letter_traces WHERE status = 'PENDING'")
                return cursor.fetchone()[0]

    def purge(self, status: str | None = None) -> int:
        """Purges dead letters, optionally filtered by status. Returns number of rows deleted."""
        with self._lock:
            with self._conn_ctx() as conn:
                with conn:
                    if status:
                        cursor = conn.execute("DELETE FROM dead_letter_traces WHERE status = ?", (status,))
                    else:
                        cursor = conn.execute("DELETE FROM dead_letter_traces")
                    return cursor.rowcount


# Global default DLQ instance
default_dlq = DeadLetterQueue()

_log = get_logger('dlq')
