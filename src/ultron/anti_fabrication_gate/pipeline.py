"""
pipeline.py — Minimal turn pipeline wiring ledger + gate + executor.

Execution order (unconditional):
  1. Create fresh EvidenceLedger for this turn
  2. Run tool(s) via tool_executor.execute_command()  [records to ledger]
  3. Build the agent's response string
  4. Call gate_response(response, ledger)             [last step before send]
  5a. If gate returns str           → send to user
  5b. If gate returns GateRejection → DO NOT send; force rewrite or re-run

The gate call at step 4 is UNCONDITIONAL — it cannot be bypassed by
any routing decision or "simple response" shortcut.
"""

from __future__ import annotations

import uuid

from evidence_ledger import EvidenceLedger
from response_gate import gate_response

from ultron.core.tool_executor import execute_command


def run_turn(
    cmd: list[str],
    response_template: str,
    *,
    turn_id: str | None = None,
) -> dict:
    """
    Execute a single pipeline turn end-to-end and return a structured result.

    Parameters
    ----------
    cmd               : the real subprocess command to run
    response_template : the agent's draft response (may contain evidence blocks)
    turn_id           : optional stable ID for this turn (auto-generated if None)

    Returns
    -------
    dict with keys:
      turn_id, ledger_snapshot, gate_decision, final_response (or None)
    """
    if turn_id is None:
        turn_id = str(uuid.uuid4())

    # Step 1 — fresh ledger
    ledger = EvidenceLedger(turn_id=turn_id)

    # Step 2 — real tool execution (records to ledger)
    tool_call_id = str(uuid.uuid4())
    execute_command(cmd, ledger, tool_call_id=tool_call_id)

    # Step 3 — agent builds response
    # (In the real system this is the LLM call; here it's passed in as the
    #  response_template parameter so we can test pass and reject cases.)
    response_draft = response_template

    # Step 4 — UNCONDITIONAL gate check
    gate_result = gate_response(response_draft, ledger)

    # Step 5 — routing based on gate decision
    if isinstance(gate_result, str):
        gate_decision = "PASS"
        final_response = gate_result
    else:  # GateRejection
        gate_decision = "REJECT"
        final_response = None   # must NOT be sent to user

    return {
        "turn_id":        turn_id,
        "tool_call_id":   tool_call_id,
        "ledger_snapshot": {
            cid: {
                "tool_name":  e.tool_name,
                "exit_code":  e.exit_code,
                "raw_stdout": e.raw_stdout,
                "raw_stderr": e.raw_stderr,
                "timestamp":  e.timestamp.isoformat(),
            }
            for cid, e in ledger.all_entries.items()
        },
        "gate_decision":  gate_decision,
        "gate_result":    gate_result,
        "final_response": final_response,
    }
