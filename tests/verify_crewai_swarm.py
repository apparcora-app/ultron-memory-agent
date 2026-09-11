import sys
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

"""
verify_crewai_swarm.py — Standalone verification harness for Ultron CrewAI Multi-Agent Swarm.

Checks:
  1. Confirms installed crewai version.
  2. Measures pre-execution telemetry audit log counts.
  3. Runs an end-to-end multi-agent execution across the Ultron squad.
  4. Verifies post-execution telemetry increments (AGENT_TASK & SWARM_RUN).
"""

import importlib.metadata
import os
import sqlite3
import sys
import time
from pathlib import Path

# Ensure local imports resolve
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Reconfigure stdout/stderr for Windows console UTF-8 support
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from crewai_pipeline import UltronCrewEngine
from telemetry import TelemetryEngine

DB_PATH = ROOT_DIR / "data" / "telemetry.db"


def get_event_counts():
    if not DB_PATH.exists():
        return 0, 0
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM audit_logs WHERE event_type = 'AGENT_TASK'")
    agent_tasks = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM audit_logs WHERE event_type = 'SWARM_RUN'")
    swarm_runs = c.fetchone()[0]
    conn.close()
    return agent_tasks, swarm_runs


def main():
    print("=" * 65)
    print(" [ULTRON PROTOCOL] CREWAI MULTI-AGENT SWARM VERIFICATION")
    print("=" * 65)

    # 1. Check CrewAI Version
    try:
        ver = importlib.metadata.version("crewai")
        print(f" [OK] CrewAI Version Installed: {ver}")
    except Exception as e:
        print(f" [WARN] Could not read crewai version via metadata: {e}")

    # 2. Pre-Execution Telemetry Audit Count
    pre_agent_tasks, pre_swarm_runs = get_event_counts()
    print(f" [TELEMETRY PRE-CHECK] AGENT_TASK events: {pre_agent_tasks} | SWARM_RUN events: {pre_swarm_runs}")

    # 3. Initialize Ultron Crew Engine
    print("\n--- Initializing Ultron CrewAI Squad ---")
    telemetry = TelemetryEngine()
    engine = UltronCrewEngine(telemetry=telemetry, use_hierarchical=True)

    print(" Squad Active Personas:")
    for k, a in engine.squad.items():
        print(f"  • [{k.upper()}]: {a.role}")

    # Explicitly verify engine properties and crew object exposure
    assert hasattr(engine, "crew"), "UltronCrewEngine must have .crew attribute"
    assert engine.crew is not None, "engine.crew must not be None"
    assert engine.agent_count == 6, f"Expected 6 agents, got {engine.agent_count}"
    assert len(engine.agents) == 6, f"Expected 6 agents in engine.agents, got {len(engine.agents)}"
    assert engine.is_hierarchical is True, "engine.is_hierarchical should be True"
    assert engine.crew.manager_agent.role == "Master Orchestrator & Strategic Planner"
    print(f" [OK] Verified UltronCrewEngine has .crew object with 6 agents ({len(engine.agents)}) in Hierarchical mode.")

    # 4. Run Multi-Agent Directive
    test_directive = "Design a high-throughput user activity ledger microservice with rate limiting and dashboard UI"
    print(f"\n--- Executing CrewAI Multi-Agent Directive ---")
    print(f" Directive: '{test_directive}'")
    print(" Processing with sequential squad pipeline...")

    t0 = time.time()
    result = engine.execute_swarm(
        directive=test_directive,
        context="System requires zero-downtime, JWT auth, and Tailwind HUD.",
        use_hierarchical=False,  # Sequential for deterministic verification
    )
    elapsed = round(time.time() - t0, 2)

    print(f"\n [OK] CrewAI Execution Complete in {elapsed}s")
    print(f" Run ID: {result['run_id']}")
    print(f" Agents Participated: {', '.join(result['agents_used'])}")
    print(f" Total Tasks Executed: {result['tasks_count']}")
    print("\n Final Deliverable Preview:")
    print("-" * 50)
    print(result["final_reply"][:400] + "...\n" if len(result["final_reply"]) > 400 else result["final_reply"])
    print("-" * 50)

    # 5. Post-Execution Telemetry Verification
    post_agent_tasks, post_swarm_runs = get_event_counts()
    print(f"\n [TELEMETRY POST-CHECK] AGENT_TASK events: {post_agent_tasks} (+{post_agent_tasks - pre_agent_tasks}) | SWARM_RUN events: {post_swarm_runs} (+{post_swarm_runs - pre_swarm_runs})")

    # Fetch latest audit entries
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute(
        "SELECT event_id, event_type, module_id, duration_ms FROM audit_logs ORDER BY timestamp DESC LIMIT 6"
    )
    rows = c.fetchall()
    conn.close()

    print("\n Latest Telemetry DB Records:")
    for r in rows:
        print(f"   • Event #{r[0]}: {r[1]} [{r[2]}] - {r[3]}ms")

    assert post_swarm_runs > pre_swarm_runs, "SWARM_RUN telemetry event was not recorded!"
    assert post_agent_tasks > pre_agent_tasks, "AGENT_TASK telemetry events were not recorded!"

    print("\n" + "=" * 65)
    print(" [SUCCESS] CrewAI Multi-Agent Swarm Verified & Instrumented 100%")
    print("=" * 65)


if __name__ == "__main__":
    main()
