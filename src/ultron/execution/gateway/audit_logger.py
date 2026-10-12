"""
audit_logger.py — Append-Only JSONL Audit Logger for Ultron Computer Execution.

Maintains an immutable, append-only JSONL audit trail capturing every intended action
(PENDING) and subsequent resolution state (PERMITTED, REFUSED, COMPLETED, FAILED) for
zero-trust forensic tracking and compliance verification.
"""

from __future__ import annotations

import json
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

try:
    sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))
    from pii_redaction import safe_redact_text
except ImportError:
    safe_redact_text = lambda x: x

from ultron.execution.computer_contracts import ActionType, AuditRecord, ComputerAction

DEFAULT_AUDIT_LOG_PATH = "./data/logs/computer_audit.jsonl"


class AuditLogger:
    """
    Thread-safe, append-only JSONL audit logger for computer actions.
    """

    def __init__(self, log_path: str = DEFAULT_AUDIT_LOG_PATH) -> None:
        self.log_path = Path(log_path).resolve()
        self._lock = threading.Lock()
        self._pending_actions: dict[str, ComputerAction] = {}
        self._ensure_log_dir()

    def _ensure_log_dir(self) -> None:
        """Ensure parent directory for the audit log exists."""
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def _append_record(self, record: AuditRecord) -> None:
        """Atomically append a single AuditRecord JSON line to the audit file."""
        json_line = record.model_dump_json() + "\n"
        json_line = safe_redact_text(json_line)
        with self._lock:
            self._ensure_log_dir()
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json_line)
                f.flush()

    def log_intent(self, action: ComputerAction) -> str:
        """
        Record action intent as PENDING before execution begins.

        Args:
            action: The ComputerAction about to be evaluated/executed.

        Returns:
            str: The generated unique record_id for correlation.
        """
        record_id = f"aud_{uuid.uuid4().hex}"
        timestamp = datetime.now(timezone.utc).isoformat()

        with self._lock:
            self._pending_actions[record_id] = action

        record = AuditRecord(
            record_id=record_id,
            timestamp=timestamp,
            action=action,
            status="PENDING",
            result_summary=None,
            error=None,
        )
        self._append_record(record)
        return record_id

    def log_result(
        self,
        record_id: str,
        status: Literal["PENDING", "PERMITTED", "REFUSED", "FAILED", "COMPLETED"] | str,
        result_summary: str | None = None,
        error: str | None = None,
    ) -> AuditRecord:
        """
        Append the execution or evaluation outcome for a previously logged action.

        Args:
            record_id: The identifier returned by log_intent.
            status: Final or intermediate status ("PERMITTED", "REFUSED", "COMPLETED", "FAILED").
            result_summary: Optional brief summary of execution result.
            error: Optional error message if refused or failed.

        Returns:
            AuditRecord: The appended audit record.
        """
        with self._lock:
            action = self._pending_actions.get(record_id)

        if action is None:
            # Fallback: attempt to find action from previous log records in the file
            action = self._find_action_by_id(record_id)
            if action is None:
                # Fallback to placeholder if unknown
                action = ComputerAction(
                    action_type=ActionType.SHELL_EXEC,
                    target="unknown",
                    payload={},
                    bot_id="unknown",
                    session_id="unknown",
                )

        timestamp = datetime.now(timezone.utc).isoformat()
        record = AuditRecord(
            record_id=record_id,
            timestamp=timestamp,
            action=action,
            status=status,  # type: ignore[arg-type]
            result_summary=result_summary,
            error=error,
        )
        self._append_record(record)
        return record

    def _find_action_by_id(self, record_id: str) -> ComputerAction | None:
        """Search log file for the action associated with record_id."""
        if not self.log_path.exists():
            return None
        try:
            with open(self.log_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    if data.get("record_id") == record_id:
                        return ComputerAction.model_validate(data["action"])
        except Exception:
            return None
        return None

    def read_all_records(self) -> list[AuditRecord]:
        """
        Read and validate all audit records from the log file.

        Returns:
            List[AuditRecord]: All recorded entries in sequential order.
        """
        records: list[AuditRecord] = []
        if not self.log_path.exists():
            return records

        with self._lock:
            with open(self.log_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        records.append(AuditRecord.model_validate_json(line))
        return records
