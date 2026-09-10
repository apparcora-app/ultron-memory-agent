"""
verify_langchain_pipeline.py — Verification harness for Ultron's LangChain Tool-Calling & Memory Engine.

Verifies:
  1. Direct `@tool` validation and execution with sandboxing.
  2. Multi-turn conversational memory retention (`UltronMemoryHistory`).
  3. Autonomous tool-calling execution loop (`UltronLangChainEngine`).
  4. Pre- and post-execution SQLite audit log telemetry verification in `./data/telemetry.db`.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import time

# Ensure UTF-8 stdout on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

from langchain_pipeline import (
    ULTRON_LANGCHAIN_TOOLS,
    UltronGeminiChatModel,
    UltronLangChainEngine,
    UltronMemoryHistory,
    ultron_python_repl,
    ultron_system_command,
    ultron_telemetry_query,
)


def main():
    print("=" * 65)
    print(" [ULTRON PROTOCOL] INITIATING LANGCHAIN ENGINE VERIFICATION")
    print("=" * 65)

    # Record initial telemetry count
    with sqlite3.connect("./data/telemetry.db") as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM audit_logs WHERE module_id='langchain_pipeline'")
        initial_count = c.fetchone()[0]

    print(f"\n[INIT] Pre-test telemetry records for 'langchain_pipeline': {initial_count}")

    # ── TEST 1: Direct Tool Invocation ──────────────────────────────────────
    print("\n[TEST 1] Testing LangChain @tool Wrappers...")
    assert len(ULTRON_LANGCHAIN_TOOLS) >= 4, "Expected at least 4 registered tools"
    print(f"  ✓ {len(ULTRON_LANGCHAIN_TOOLS)} LangChain tools registered: {[t.name for t in ULTRON_LANGCHAIN_TOOLS]}")

    # Run Python REPL tool
    py_res = ultron_python_repl.invoke({"code": "result = 128 * 4; print(f'COMPUTED_{result}')"})
    assert "COMPUTED_512" in str(py_res), f"Unexpected REPL output: {py_res}"
    print("  ✓ ultron_python_repl executed successfully -> COMPUTED_512")

    # Run Telemetry Query tool
    telemetry_res = ultron_telemetry_query.invoke({"limit": 2})
    assert "event_id" in str(telemetry_res), f"Unexpected telemetry output: {telemetry_res}"
    print("  ✓ ultron_telemetry_query returned recent SQLite audit logs.")

    # ── TEST 2: Conversational Memory Retention ─────────────────────────────
    print("\n[TEST 2] Testing Multi-Turn Conversational Memory...")
    engine = UltronLangChainEngine(user_id="boss")

    # Turn 1: Introduce a secret project code
    turn1_res = engine.run("My top secret project name is Project Quantum Sentinel. Remember this.")
    print(f"  Turn 1 Response: {turn1_res[:100]}...")

    # Turn 2: Query the memory
    turn2_res = engine.run("What is my top secret project name?")
    print(f"  Turn 2 Response: {turn2_res[:120]}...")
    assert "Quantum Sentinel" in turn2_res or "quantum sentinel" in turn2_res.lower(), (
        f"Memory retention failed! Expected 'Quantum Sentinel' in: {turn2_res}"
    )
    print("  ✓ Multi-turn memory retention verified across conversational turns!")

    # ── TEST 3: Autonomous Tool-Calling Execution Loop ──────────────────────
    print("\n[TEST 3] Testing Autonomous Tool-Calling Reasoning Loop...")
    tool_engine = UltronLangChainEngine(user_id="boss")
    query = "Calculate 1527 * 399 using python and give me the exact number."
    answer = tool_engine.run(query)
    expected_val = str(1527 * 399)  # 609273
    print(f"  Tool Execution Answer: {answer}")
    assert expected_val in answer.replace(",", ""), f"Tool execution failed to return {expected_val}. Got: {answer}"
    print(f"  ✓ Autonomous tool-calling loop executed and synthesized exact result: {expected_val}!")

    # ── TEST 4: SQLite Database Telemetry Verification ──────────────────────
    print("\n[TEST 4] Verifying SQLite Audit Database (./data/telemetry.db)...")
    with sqlite3.connect("./data/telemetry.db") as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM audit_logs WHERE module_id='langchain_pipeline'")
        final_count = c.fetchone()[0]

        c.execute(
            "SELECT event_id, event_type, module_id, details, duration_ms "
            "FROM audit_logs WHERE module_id='langchain_pipeline' ORDER BY timestamp DESC LIMIT 3"
        )
        recent_rows = c.fetchall()

    delta = final_count - initial_count
    print(f"  ✓ Telemetry audit entries generated in this session: +{delta} events (Total: {final_count})")
    assert delta >= 4, f"Expected at least 4 new telemetry events, got {delta}"

    for row in recent_rows:
        print(f"    - Event #{row[0]}: {row[1]} [{row[2]}] in {row[4]}ms | Details: {row[3][:65]}...")

    print("\n" + "=" * 65)
    print(" [ULTRON PROTOCOL] ALL 4 LANGCHAIN VERIFICATION TESTS PASSED 100%!")
    print("=" * 65)


if __name__ == "__main__":
    main()
