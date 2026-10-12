import sys
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

"""
verify_langgraph_handoff.py — Standalone verification harness for LangGraph 2-step handoff.
Validates state machine cyclic handoffs between Titan and Nexus.
"""

import importlib.metadata
import os
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
    db_path = ROOT_DIR / "data" / "telemetry.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS audit_logs (event_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, event_type TEXT NOT NULL, module_id TEXT NOT NULL, details TEXT, duration_ms INTEGER, timestamp REAL)")
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM audit_logs WHERE event_type = 'AGENT_TASK'")
    initial_agent_tasks = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM audit_logs WHERE event_type = 'SWARM_RUN'")
    initial_swarm_runs = cursor.fetchone()[0]
    conn.close()

    print("[CHECK 2] Pre-Execution Telemetry Counts:")
    print(f"          - AGENT_TASK events in DB: {initial_agent_tasks}")
    print(f"          - SWARM_RUN events in DB:  {initial_swarm_runs}\n")

    # 3. Execute the LangGraph StateGraph Pipeline
    print("[CHECK 3] Initializing and Executing LangGraph StateGraph (START -> Titan -> Nexus -> END)...")
    telemetry = TelemetryEngine()
    pipeline = LangGraphTwoStepSwarm(telemetry=telemetry)

    test_directive = "Design a high-speed telemetry event ingestion pipeline and a real-time stream viewer component."
    result = pipeline.execute(directive=test_directive, context="Ultron Cybernetic Core v2.5", user_id="boss")

    print("\n" + "-" * 68)
    print("Execution Finished! Final StateGraph Artifacts:")
    print(f"  Final Node Handoff: {result.get('current_agent')}")
    print(f"  Directive Processed: {result.get('directive')}")
    print(f"  Titan Architecture Output: {result.get('titan_output')[:100]}...")
    print(f"  Nexus Interface Output:    {result.get('nexus_output')[:100]}...")
    print("-" * 68 + "\n")

    # FIX 1: Explicitly check the output for errors instead of just relying on telemetry
    titan_out = str(result.get('titan_output', ''))
    nexus_out = str(result.get('nexus_output', ''))
    
    assert titan_out, "Titan output is empty"
    assert nexus_out, "Nexus output is empty"
    # Structural check on the API response status rather than brittle string matching
    titan_status = result.get('titan_status')
    nexus_status = result.get('nexus_status')
    errors = result.get('errors', [])
    assert titan_status == 'COMPLETED', f"Titan node failed structurally with status: {titan_status}. Output: {titan_out}"
    assert nexus_status == 'COMPLETED', f"Nexus node failed structurally with status: {nexus_status}. Output: {nexus_out}"
    assert not errors, f"Pipeline accumulated errors: {errors}"
    
    # 4. Verify Telemetry Post-Execution
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM audit_logs WHERE event_type = 'AGENT_TASK'")
    post_agent_tasks = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM audit_logs WHERE event_type = 'SWARM_RUN'")
    post_swarm_runs = cursor.fetchone()[0]
    conn.close()

    print("[CHECK 4] Post-Execution Telemetry Counts:")
    print(f"          - AGENT_TASK events in DB: {post_agent_tasks} (Expected >= {initial_agent_tasks + 2})")
    print(f"          - SWARM_RUN events in DB:  {post_swarm_runs} (Expected >= {initial_swarm_runs + 1})")

    assert post_agent_tasks >= initial_agent_tasks + 2, f"Failed: Expected at least 2 AGENT_TASK events logged, got {post_agent_tasks - initial_agent_tasks}"
    assert post_swarm_runs >= initial_swarm_runs + 1, f"Failed: Expected at least 1 SWARM_RUN event logged, got {post_swarm_runs - initial_swarm_runs}"

    print("\n" + "=" * 68)
    print("  [SUCCESS] All LangGraph Verification Checks Passed Cleanly!")
    print("=" * 68)


if __name__ == "__main__":
    main()
