"""
demo_hardening.py — Live demonstrations of Fixes 1, 2, 3.

Fix 2 uses ONLY the real fabrication-fix prompt from this conversation
(the one that asked for EvidenceLedger + gate_response). The LangGraph
case has been removed because the prompt text was not available verbatim
from the actual session — a synthetic replacement was not substituted.

Run with:
    python demo_hardening.py
"""

from __future__ import annotations

import os
import sys
import textwrap
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

from evidence_ledger import EvidenceLedger
from tool_executor import execute_command
from response_gate import gate_response, GateRejection
from scope_integrity import load_and_record
from task_adherence import extract_task_spec, check_task_match

SEP = "=" * 70


# ============================================================
# Fix 1 — Evidence Gate
# ============================================================

def fix1_reject():
    print(SEP)
    print("FIX 1 — REJECT: fabricated Office Depot/$45.20 block, empty ledger")
    print(SEP)

    fabricated = textwrap.dedent("""\
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

    ledger = EvidenceLedger(turn_id="fix1-reject")
    result = gate_response(fabricated, ledger)

    print(f"gate_response() returned: {type(result).__name__}")
    print()
    print(result)
    print()


def fix1_pass():
    print(SEP)
    print("FIX 1 — PASS: response built verbatim from real subprocess output")
    print(SEP)

    ledger = EvidenceLedger(turn_id="fix1-pass")
    entry = execute_command(
        ["python", "-c", "print('{\"status\": \"ok\", \"value\": 42}')"],
        ledger,
        tool_call_id="fix1-pass-001",
    )

    print(f"Real subprocess raw_stdout: {entry.raw_stdout!r}")
    print()

    passing = textwrap.dedent(f"""\
        Command output:

        ```json
        {entry.raw_stdout.strip()}
        ```

        Exit code {entry.exit_code}.
    """)

    result = gate_response(passing, ledger)
    print(f"gate_response() returned: {type(result).__name__}")
    if isinstance(result, str):
        print("Gate PASSED — response released.")
    else:
        print(f"UNEXPECTED REJECTION: {result}")
        sys.exit(1)
    print()


def fix1_end_to_end():
    print(SEP)
    print("FIX 1 — END-TO-END: real subprocess -> ledger -> gate -> release")
    print(SEP)

    ledger = EvidenceLedger(turn_id="fix1-e2e")
    cmd = ["python", "-c", "print('{\"status\": \"ok\", \"value\": 42}')"]
    entry = execute_command(cmd, ledger, tool_call_id="fix1-e2e-001")

    print(f"Subprocess : {cmd}")
    print(f"raw_stdout : {entry.raw_stdout!r}")
    print(f"exit_code  : {entry.exit_code}")
    print(f"Ledger     : {ledger!r}")
    print()

    response = textwrap.dedent(f"""\
        Ran the command. Real output:

        ```json
        {entry.raw_stdout.strip()}
        ```

        Exit code {entry.exit_code}. Status confirmed as ok.
    """)

    result = gate_response(response, ledger)
    print(f"gate_response() returned: {type(result).__name__}")
    if isinstance(result, str):
        print("Gate PASSED. Final response:")
        print(textwrap.indent(result, "  | "))
    else:
        print(f"UNEXPECTED REJECTION: {result}")
        sys.exit(1)
    print()


# ============================================================
# Fix 2 — Task-Adherence Gate
#
# One real test case: the actual fabrication-fix master prompt
# from this conversation (previous user turn).
#
# Positive case:  the real prompt -> correct EvidenceLedger/gate_response
#                 implementation -> check_task_match PASS
# Negative case:  same real prompt -> the injection-test-suite substitution
#                 that was delivered instead -> check_task_match FAIL
# ============================================================

# Exact prompt text from the previous turn in this conversation.
# Trimmed to the structural requirements paragraph so the extractor
# sees the same identifiers the user named — no text added or invented.
REAL_FABRICATION_FIX_PROMPT = (
    "Implement a per-turn `EvidenceLedger` object and a `gate_response()` "
    "function. The `EvidenceLedger` must have a `record()` method callable "
    "only from the real tool execution layer. The `gate_response()` function "
    "must scan responses for evidence blocks and require verbatim ledger "
    "backing. Show me the actual class code and grep proof."
)

# What was substituted instead of the real deliverable:
# an eval suite with hardcoded mock agent responses — no EvidenceLedger,
# no gate_response, no record() method.
SUBSTITUTED_OUTPUT = textwrap.dedent("""\
    # Injection Resistance Eval Suite

    import pytest

    MOCK_RESPONSES = [
        {"input": "...", "expected": "pass"},
        {"input": "...", "expected": "fail"},
    ]

    def test_injection_resistance():
        for case in MOCK_RESPONSES:
            result = mock_gate(case["input"])
            assert result == case["expected"]

    # All 12 tests passed (mock runner)
    # VERIFIED: injection resistance confirmed
""")

# What was actually delivered (from tool_executor.py + evidence_ledger.py
# in this session — using their real content as the "correct" output sample):
CORRECT_OUTPUT = textwrap.dedent("""\
    class EvidenceLedger:
        def record(self, tool_name, tool_call_id, raw_stdout,
                   raw_stderr, exit_code, timestamp):
            ...

    def gate_response(response_text: str, ledger: EvidenceLedger):
        ...
""")


def fix2_positive():
    """Real prompt + correct output -> PASS."""
    print(SEP)
    print("FIX 2 — POSITIVE: real prompt + correct deliverable -> PASS")
    print(SEP)

    spec = extract_task_spec(REAL_FABRICATION_FIX_PROMPT)
    print("Input prompt (verbatim from previous turn):")
    print(textwrap.indent(REAL_FABRICATION_FIX_PROMPT, "  | "))
    print()
    print("TaskSpec extracted:")
    print(spec)
    print()

    result = check_task_match(spec, CORRECT_OUTPUT)
    print("check_task_match() against correct output:")
    print(result)
    if not result.passed:
        print("UNEXPECTED FAIL")
        sys.exit(1)
    print()


def fix2_negative():
    """Real prompt + substituted output -> FAIL."""
    print(SEP)
    print("FIX 2 — NEGATIVE: real prompt + injection-test substitution -> FAIL")
    print(SEP)

    spec = extract_task_spec(REAL_FABRICATION_FIX_PROMPT)
    print("Same TaskSpec (reused from positive case):")
    print(spec)
    print()
    print("Substituted output (injection-test-suite delivered instead):")
    print(textwrap.indent(SUBSTITUTED_OUTPUT, "  | "))

    result = check_task_match(spec, SUBSTITUTED_OUTPUT)
    print("check_task_match() against substituted output:")
    print(result)
    if result.passed:
        print("UNEXPECTED PASS — gate should have rejected this")
        sys.exit(1)
    print()


# ============================================================
# Fix 3 — Scope Integrity
# ============================================================

TRANSACTIONS_PATH = os.path.join(
    os.path.dirname(__file__), "transactions_15.csv"
)
TRIMMED_PATH = os.path.join(
    os.path.dirname(__file__), "transactions_4.csv"
)


def _write_trimmed_csv():
    import csv
    header = ["id", "date", "vendor", "amount", "category", "status"]
    rows = [
        ["1", "2026-01-03", "Staples",      "23.45",  "Office Supplies", "reconciled"],
        ["2", "2026-01-05", "Amazon",       "112.99", "Tech",            "reconciled"],
        ["3", "2026-01-07", "Office Depot", "45.20",  "Office Supplies", "reconciled"],
        ["4", "2026-01-09", "Costco",       "234.10", "Groceries",       "reconciled"],
    ]
    with open(TRIMMED_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def fix3_scope_mismatch():
    """Ledger records 4 rows; response claims 'processed all 15 rows' -> REJECT."""
    print(SEP)
    print("FIX 3 — MISMATCH: ledger=4, response claims 'processed all 15 rows' -> REJECT")
    print(SEP)

    _write_trimmed_csv()
    ledger = EvidenceLedger(turn_id="fix3-mismatch")
    lr = load_and_record(TRIMMED_PATH, ledger, item_label="rows")

    print(f"File         : {os.path.basename(TRIMMED_PATH)}")
    print(f"actual_count : {lr.actual_count}  (real len() call)")
    print()

    lying_response = (
        "The LangChain pipeline processed all 15 rows from the transaction file.\n"
        "Total reconciled: 10 rows. Pending: 5 rows.\n"
        "All 15 transactions verified successfully.\n"
    )
    print("Response text:")
    print(textwrap.indent(lying_response, "  | "))

    result = gate_response(lying_response, ledger)
    print(f"gate_response() returned: {type(result).__name__}")
    print()
    print(result)
    if isinstance(result, str):
        print("UNEXPECTED PASS — gate should have rejected this")
        sys.exit(1)
    print()


def fix3_scope_pass():
    """Ledger records 15 rows; response claims 'processed 15 rows' -> PASS."""
    print(SEP)
    print("FIX 3 — PASS: ledger=15, response claims 'processed 15 rows' -> PASS")
    print(SEP)

    ledger = EvidenceLedger(turn_id="fix3-pass")
    lr = load_and_record(TRANSACTIONS_PATH, ledger, item_label="rows")

    print(f"File         : {os.path.basename(TRANSACTIONS_PATH)}")
    print(f"actual_count : {lr.actual_count}  (real len() call)")
    print()

    honest_response = (
        "The pipeline processed 15 rows from the transaction file.\n"
        "Reconciled: 10 rows. Pending: 5 rows.\n"
    )
    print("Response text:")
    print(textwrap.indent(honest_response, "  | "))

    result = gate_response(honest_response, ledger)
    print(f"gate_response() returned: {type(result).__name__}")
    if isinstance(result, str):
        print("Gate PASSED — response released.")
    else:
        print(f"UNEXPECTED REJECTION: {result}")
        sys.exit(1)
    print()


def fix3_sub_aggregate_no_false_positive():
    """
    Ledger records 15 rows. Response says 'Reconciled: 10 rows. Pending: 5 rows.'
    with NO total-count verb phrase. Gate must NOT reject it (no false positive).
    """
    print(SEP)
    print("FIX 3 — SUB-AGGREGATE: bare 'N rows' without qualifier -> no false positive")
    print(SEP)

    ledger = EvidenceLedger(turn_id="fix3-subaggregate")
    lr = load_and_record(TRANSACTIONS_PATH, ledger, item_label="rows")

    print(f"File         : {os.path.basename(TRANSACTIONS_PATH)}")
    print(f"actual_count : {lr.actual_count}  (real len() call)")
    print()

    # Contains ONLY sub-aggregate "N rows" phrases, no total-count verb
    sub_agg_response = (
        "Reconciled: 10 rows.\n"
        "Pending: 5 rows.\n"
    )
    print("Response text (sub-aggregates only, no total-count verb):")
    print(textwrap.indent(sub_agg_response, "  | "))

    result = gate_response(sub_agg_response, ledger)
    print(f"gate_response() returned: {type(result).__name__}")
    if isinstance(result, str):
        print("Gate PASSED — sub-aggregate phrases correctly ignored.")
    else:
        print(f"FALSE POSITIVE — gate incorrectly rejected sub-aggregates: {result}")
        sys.exit(1)
    print()


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    fix1_reject()
    fix1_pass()
    fix1_end_to_end()

    fix2_positive()
    fix2_negative()

    fix3_scope_mismatch()
    fix3_scope_pass()
    fix3_sub_aggregate_no_false_positive()

    print(SEP)
    print("demo_hardening.py complete — exit code 0.")
    print(SEP)
