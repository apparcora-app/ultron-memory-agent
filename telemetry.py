"""
telemetry.py — Layer 8: Ops & Governance Layer (Telemetry, Prometheus Metrics & Audit DB).

Logs operational audit events, token usage metrics, tool execution counts,
and generates Prometheus-compatible metrics text for observability.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class AuditEvent:
    event_id: str
    user_id: str
    event_type: str  # TOOL_CALL, CHAT_TURN, MEMORY_UPDATE, SWARM_RUN, AGENT_TASK
    module_id: str
    details: dict[str, Any]
    duration_ms: int
    timestamp: float = time.time()


class TelemetryEngine:
    """
    Observability, Auditing, and Prometheus Metrics Exporter.
    Implements Layer 8 of the Agentic AI Architecture.
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        if db_path is None:
            self.db_path = Path(__file__).parent / "data" / "telemetry.db"
        else:
            p = Path(db_path)
            self.db_path = p if p.is_absolute() else (Path(__file__).parent / p)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._start_time = time.time()
        self._init_db()

        # Counter metrics
        self._total_requests = 0
        self._total_tool_calls = 0
        self._total_swarm_runs = 0
        self._total_agent_tasks = 0
        self._total_prompt_optimizations = 0
        self._total_errors = 0
        self._total_tokens_input = 0
        self._total_tokens_output = 0

        # Load historical counts from DB
        self._load_historical_counts()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                event_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                module_id TEXT NOT NULL,
                details TEXT,
                duration_ms INTEGER,
                timestamp REAL
            )
        """)
        conn.commit()
        conn.close()

    def _load_historical_counts(self) -> None:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM audit_logs")
            self._total_requests = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM audit_logs WHERE event_type = 'TOOL_CALL'")
            self._total_tool_calls = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM audit_logs WHERE event_type = 'SWARM_RUN'")
            self._total_swarm_runs = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM audit_logs WHERE event_type = 'AGENT_TASK'")
            self._total_agent_tasks = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM audit_logs WHERE event_type = 'PROMPT_OPTIMIZED'")
            self._total_prompt_optimizations = cursor.fetchone()[0]
            conn.close()
        except Exception:
            pass

    def log_event(self, user_id: str, event_type: str, module_id: str, details: dict[str, Any], duration_ms: int = 0) -> str:
        """Record an audit log event into SQLite."""
        event_id = f"evt_{uuid.uuid4().hex[:10]}"
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO audit_logs VALUES (?, ?, ?, ?, ?, ?, ?)",
            (event_id, user_id, event_type, module_id, json.dumps(details), duration_ms, time.time()),
        )
        conn.commit()
        conn.close()

        # Update metrics counters
        self._total_requests += 1
        if event_type == "TOOL_CALL":
            self._total_tool_calls += 1
        elif event_type == "SWARM_RUN":
            self._total_swarm_runs += 1
        elif event_type == "AGENT_TASK":
            self._total_agent_tasks += 1
        elif event_type == "PROMPT_OPTIMIZED":
            self._total_prompt_optimizations += 1

        if details.get("error") or not details.get("success", True):
            self._total_errors += 1

        tokens = details.get("tokens", {})
        self._total_tokens_input += tokens.get("input", 0)
        self._total_tokens_output += tokens.get("output", 0)

        return event_id

    def generate_prometheus_metrics(self) -> str:
        """Generate standard Prometheus metric text format."""
        uptime = time.time() - self._start_time
        lines = [
            "# HELP ultron_uptime_seconds Total running time of Ultron Cybernetic Core.",
            "# TYPE ultron_uptime_seconds gauge",
            f"ultron_uptime_seconds {uptime:.2f}",
            "",
            "# HELP ultron_requests_total Total chat requests processed.",
            "# TYPE ultron_requests_total counter",
            f"ultron_requests_total {self._total_requests}",
            "",
            "# HELP ultron_prompt_optimizations_total Total prompts optimized via Prompt Architect.",
            "# TYPE ultron_prompt_optimizations_total counter",
            f"ultron_prompt_optimizations_total {self._total_prompt_optimizations}",
            "",
            "# HELP ultron_swarm_runs_total Total multi-agent swarm orchestrations.",
            "# TYPE ultron_swarm_runs_total counter",
            f"ultron_swarm_runs_total {self._total_swarm_runs}",
            "",
            "# HELP ultron_agent_tasks_total Total subagent tasks executed across swarm.",
            "# TYPE ultron_agent_tasks_total counter",
            f"ultron_agent_tasks_total {self._total_agent_tasks}",
            "",
            "# HELP ultron_tool_calls_total Total tool executions.",
            "# TYPE ultron_tool_calls_total counter",
            f"ultron_tool_calls_total {self._total_tool_calls}",
            "",
            "# HELP ultron_errors_total Total execution errors.",
            "# TYPE ultron_errors_total counter",
            f"ultron_errors_total {self._total_errors}",
            "",
            "# HELP ultron_tokens_input_total Total input tokens consumed.",
            "# TYPE ultron_tokens_input_total counter",
            f"ultron_tokens_input_total {self._total_tokens_input}",
            "",
            "# HELP ultron_tokens_output_total Total output tokens generated.",
            "# TYPE ultron_tokens_output_total counter",
            f"ultron_tokens_output_total {self._total_tokens_output}",
        ]
        return "\n".join(lines) + "\n"

    def get_recent_logs(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retrieve recent audit logs from SQLite."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()

        logs = []
        for r in rows:
            logs.append({
                "event_id": r["event_id"],
                "user_id": r["user_id"],
                "event_type": r["event_type"],
                "module_id": r["module_id"],
                "details": json.loads(r["details"]) if r["details"] else {},
                "duration_ms": r["duration_ms"],
                "timestamp": r["timestamp"],
            })
        return logs
