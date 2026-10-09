import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from execution_ledger_gate import ExecutionLedgerGate
from core.tool_definitions import ToolExecutor

def main():
    ledger_gate = ExecutionLedgerGate()
    executor = ToolExecutor()
    
    # Mock LLM generating a python block without calling tools, but claiming it did
    draft_reply = "I have calculated the fibonacci sequence for you. Here is the script:\n`python\ndef fib(n):\n    pass\n`\nIt executed successfully and the output was 10."
    tool_actions = []
    
    # Run Ledger Gate
    try:
        reply, actions, report = ledger_gate.verify_and_enforce(
            user_input="Please calculate fibonacci.",
            draft_reply=draft_reply,
            tool_actions=tool_actions,
            tool_executor=executor
        )
        if report and not report.all_verified:
            print("=== LEDGER GATE TRIGGERED ===")
            for v in report.violations:
                print("Violation:", v)
            print("Remediation:", report.remediation_instructions)
    except Exception as e:
        print("LEDGER ERROR:", e)

if __name__ == '__main__':
    main()
