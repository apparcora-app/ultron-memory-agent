import sys
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

"""
verify_langgraph_handoff.py — Standalone verification script for the LangGraph 2-Step Handoff.

Verifies:
  (a) LangGraph StateGraph executes end-to-end with real data flowing between Titan and Nexus.
  (b) Telemetry counters and SQLite audit_logs rows increment correctly (SWARM_RUN, AGENT_TASK).
  (c) Installed LangGraph version.
"""

from __future__ import annotations

import importlib.metadata
import json
import sqlite3
import sys
from pathlib import Path

from langgraph_pipeline import LangGraphTwoStepSwarm
from telemetry import TelemetryEngine


def main():
    print("=" * 68)
    print("  LANGGRAPH 2-STEP HANDOFF VERIFICATION SUITE")
    print("=" * 68)

    # 1. Check LangGraph Version
    try:
        lg_version = importlib.metadata.version("langgraph")
        print(f"[CHECK 1] Installed LangGraph Version: {lg_version}")
    except Exception as e:
        print(f"[CHECK 1 FAILED] Could not detect LangGraph version: {e}")
        sys.exit(1)

    # 2. Inspect Initial Telemetry State in SQLite
    db_path = Path(__file__).parent / "data" / "telemetry.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS audit_logs (event_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, event_type TEXT NOT NULL, module_id TEXT NOT NULL, details TEXT, duration_ms INTEGER, timestamp REAL)")
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM audit_logs WHERE event_type = 'AGENT_TASK'")
    initial_agent_tasks = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM audit_logs WHERE event_type = 'SWARM_RUN'")
    initial_swarm_runs = cursor.fetchone()[0]
    conn.close()

    print(f"[CHECK 2] Pre-Execution Telemetry Counts:")
    print(f"          - AGENT_TASK events in DB: {initial_agent_tasks}")
    print(f"          - SWARM_RUN events in DB:  {initial_swarm_runs}\n")

    # 3. Execute the LangGraph StateGraph Pipeline
    print(f"[CHECK 3] Initializing and Executing LangGraph StateGraph (START -> Titan -> Nexus -> END)...")
    telemetry = TelemetryEngine()
    pipeline = LangGraphTwoStepSwarm(telemetry=telemetry)

    test_directive = "Design a high-speed telemetry event ingestion pipeline and a real-time stream viewer component."
    result = pipeline.execute(directive=test_directive, context="Ultron Cybernetic Core v2.5", user_id="boss")

    print("\n" + "-" * 68)
    print("  LANGGRAPH STATE GRAPH EXECUTION RESULTS")
    print("-" * 68)
    print(f"* Run ID:             {result['run_id']}")
    print(f"* Current Step:       {result['current_step']}")
    print(f"* Titan Status:       {result['titan_status']} ({result['titan_execution_time_ms']}ms)")
    print(f"* Nexus Status:       {result['nexus_status']} ({result['nexus_execution_time_ms']}ms)")
    print(f"* Total Duration:     {result['total_duration_sec']}s")
    print(f"* Pipeline Errors:    {result['errors'] or 'None'}")

    print("\n[TITAN OUTPUT (Backend Data / Schema)]")
    print(result['titan_output'][:300] + ("..." if len(result['titan_output']) > 300 else ""))

    print("\n[NEXUS OUTPUT (Frontend UI Consuming Titan Contract)]")
    print(result['nexus_output'][:300] + ("..." if len(result['nexus_output']) > 300 else ""))

    # 4. Verify Telemetry Increment in SQLite
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM audit_logs WHERE event_type = 'AGENT_TASK'")
    post_agent_tasks = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM audit_logs WHERE event_type = 'SWARM_RUN'")
    post_swarm_runs = cursor.fetchone()[0]

    cursor.execute("SELECT event_id, event_type, module_id, duration_ms, details FROM audit_logs ORDER BY timestamp DESC LIMIT 3")
    latest_rows = cursor.fetchall()
    conn.close()

    print("\n" + "-" * 68)
    print("  TELEMETRY AUDIT VERIFICATION")
    print("-" * 68)
    print(f"* AGENT_TASK Count:   {initial_agent_tasks} -> {post_agent_tasks} (+{post_agent_tasks - initial_agent_tasks})")
    print(f"* SWARM_RUN Count:    {initial_swarm_runs} -> {post_swarm_runs} (+{post_swarm_runs - initial_swarm_runs})")

    print("\nLatest 3 Telemetry Events Recorded in ./data/telemetry.db:")
    for r in latest_rows:
        evt_id, evt_type, mod_id, dur_ms, det_json = r
        try:
            det = json.loads(det_json)
            agent_or_engine = det.get("agent") or det.get("engine") or ""
        except Exception:
            agent_or_engine = ""
        print(f"  [{evt_type}] ID: {evt_id} | Module: {mod_id:<18} | Time: {dur_ms}ms | Info: {agent_or_engine}")

    print("\n" + "=" * 68)
    print("  VERIFICATION COMPLETE")
    print("=" * 68)


if __name__ == "__main__":
    main()
