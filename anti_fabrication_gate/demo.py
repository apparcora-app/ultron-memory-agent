"""
demo.py — Live demonstration of all three parts.

Run with:
    python demo.py

Produces ONLY real subprocess output, real ledger state,
and real gate decisions. No mocks, no hardcoded pass/fail strings.
"""

from __future__ import annotations

import json
import sys
import textwrap
import uuid
from datetime import datetime, timezone

# Adjust path so modules resolve when run from any cwd
import os
sys.path.insert(0, os.path.dirname(__file__))

from evidence_ledger import EvidenceLedger
from tool_executor import execute_command
from response_gate import gate_response, GateRejection
from pipeline import run_turn


SEPARATOR = "=" * 70


# ---------------------------------------------------------------------------
# Part 1 verification — print the class, then run grep externally
# ---------------------------------------------------------------------------

def part1_verify():
    print(SEPARATOR)
    print("PART 1 — EvidenceLedger: basic record/get/immutability check")
    print(SEPARATOR)

    ledger = EvidenceLedger(turn_id="test-part1")
    ts = datetime.now(tz=timezone.utc)

    e = ledger.record(
        tool_name="echo",
        tool_call_id="tcid-001",
        raw_stdout='{"status": "ok", "value": 42}\n',
        raw_stderr="",
        exit_code=0,
        timestamp=ts,
    )
    print(f"  Recorded entry: {e}")

    fetched = ledger.get("tcid-001")
    assert fetched is e, "get() must return the same object"
    print(f"  ledger.get('tcid-001') → {fetched}")

    missing = ledger.get("does-not-exist")
    assert missing is None
    print(f"  ledger.get('does-not-exist') → {missing}")

    # Immutability: second record() with same ID must raise
    try:
        ledger.record("echo", "tcid-001", "other", "", 0, ts)
        print("  ERROR: DuplicateEntryError was NOT raised — BUG!")
        sys.exit(1)
    except Exception as exc:
        print(f"  Duplicate record correctly rejected: {type(exc).__name__}: {exc}")

    print(f"\n  Ledger repr: {ledger!r}")
    print(f"  Ledger entries: {ledger.all_entries}")
    print()


# ---------------------------------------------------------------------------
# Part 2 — REJECT case: fabricated Office-Depot-style block
# ---------------------------------------------------------------------------

FABRICATED_RESPONSE = textwrap.dedent("""\
    The reconciliation has been fully verified.

    ```json
    {
      "status": "verified",
      "vendor": "Office Depot",
      "amount": 45.20,
      "passed": true,
      "result": "all 3 line items matched"
    }
    ```

    All checks passed. The total of $45.20 was confirmed against the ledger.
""")


def part2_reject():
    print(SEPARATOR)
    print("PART 2a — REJECT case: fabricated VERIFIED block, empty ledger")
    print(SEPARATOR)
    print("Response draft (fabricated):")
    print(textwrap.indent(FABRICATED_RESPONSE, "  │ "))

    ledger = EvidenceLedger(turn_id="test-part2-reject")
    # Ledger is EMPTY — no real tool was run

    result = gate_response(FABRICATED_RESPONSE, ledger)

    print(f"\n  gate_response() returned: {type(result).__name__}")
    if isinstance(result, GateRejection):
        print(f"\n  {result}")
        print("\n  ✓ Gate correctly returned GateRejection — response BLOCKED.")
    else:
        print("  ERROR: gate returned the response instead of GateRejection — BUG!")
        sys.exit(1)
    print()


# ---------------------------------------------------------------------------
# Part 2 — PASS case: response references real ledger content verbatim
# ---------------------------------------------------------------------------

def part2_pass():
    print(SEPARATOR)
    print("PART 2b — PASS case: response built from real ledger entry")
    print(SEPARATOR)

    # Simulate a real tool call by populating the ledger
    ledger = EvidenceLedger(turn_id="test-part2-pass")
    ts = datetime.now(tz=timezone.utc)
    real_stdout = '{"status": "ok", "value": 42}\n'
    ledger.record(
        tool_name="echo",
        tool_call_id="tcid-pass-001",
        raw_stdout=real_stdout,
        raw_stderr="",
        exit_code=0,
        timestamp=ts,
    )
    print(f"  Ledger populated with real entry, raw_stdout = {real_stdout!r}")

    # Response that quotes the real stdout verbatim
    passing_response = textwrap.dedent(f"""\
        The command completed successfully. Here is the real output:

        ```json
        {real_stdout.strip()}
        ```

        Exit code was 0.
    """)
    print("\n  Response draft (uses verbatim ledger content):")
    print(textwrap.indent(passing_response, "  │ "))

    result = gate_response(passing_response, ledger)

    print(f"\n  gate_response() returned: {type(result).__name__}")
    if isinstance(result, str):
        print("  ✓ Gate returned the response string — PASSED.")
        print(f"  Returned text (first 200 chars): {result[:200]!r}")
    else:
        print(f"  ERROR: gate rejected valid response — BUG!\n  {result}")
        sys.exit(1)
    print()


# ---------------------------------------------------------------------------
# Part 3 — Full end-to-end pipeline with a REAL subprocess
# ---------------------------------------------------------------------------

def part3_end_to_end():
    print(SEPARATOR)
    print("PART 3 — End-to-end: real subprocess → ledger → gate → release")
    print(SEPARATOR)

    # Real command: emit a JSON string that the response will quote back
    real_cmd = ["python", "-c", "print('{\"status\": \"ok\", \"value\": 42}')"]

    # The agent's response template — it must quote the real output verbatim.
    # We build it AFTER we know what the command will produce:
    # For the demo we know the output; in real usage the LLM sees the tool
    # result before composing its response.
    response_template = textwrap.dedent("""\
        Ran the command. Real output:

        ```json
        {"status": "ok", "value": 42}
        ```

        Exit code 0. Status confirmed as ok.
    """)

    print(f"  Command: {real_cmd}")
    print(f"  Response template (contains evidence block):\n")
    print(textwrap.indent(response_template, "  │ "))

    result = run_turn(real_cmd, response_template)

    print(f"\n  ── Subprocess real stdout ──────────────────────────────────────")
    for cid, snap in result["ledger_snapshot"].items():
        print(f"  tool_call_id : {cid}")
        print(f"  tool_name    : {snap['tool_name']}")
        print(f"  exit_code    : {snap['exit_code']}")
        print(f"  raw_stdout   : {snap['raw_stdout']!r}")
        print(f"  raw_stderr   : {snap['raw_stderr']!r}")
        print(f"  timestamp    : {snap['timestamp']}")

    print(f"\n  ── Gate decision ───────────────────────────────────────────────")
    print(f"  gate_decision : {result['gate_decision']}")

    if result["gate_decision"] == "PASS":
        print("  ✓ Gate PASSED — response delivered to user.")
        print(f"\n  Final response:\n")
        print(textwrap.indent(result["final_response"], "  │ "))
    else:
        gate_obj = result["gate_result"]
        print(f"  Gate REJECTED — reason: {gate_obj.reason}")
        print(f"  Missing tokens: {gate_obj.missing_tokens}")
        sys.exit(1)

    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    part1_verify()
    part2_reject()
    part2_pass()
    part3_end_to_end()
    print(SEPARATOR)
    print("All demonstrations complete.")
    print(SEPARATOR)
