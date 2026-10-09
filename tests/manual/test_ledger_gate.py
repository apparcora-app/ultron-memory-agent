import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import asyncio
from agent import MemoryAgent

async def main():
    agent = MemoryAgent()
    
    # 1. Bypass Mem0 and MCP loading so the test runs instantly
    agent._memory.detect_and_store_emotional_context = lambda x: None
    agent._tool_executor._mcp_tools_loaded = True
    agent._tool_executor._mcp_tools = {}
    
    # 2. Patch the print in agent.py to show the exact audit trail for proof
    original_verify = agent._ledger_gate.verify_and_enforce
    def mock_verify(*args, **kwargs):
        draft, actions, report = original_verify(*args, **kwargs)
        if not report.all_verified:
            for trace in report.audit_trail:
                if trace.startswith('?') or trace.startswith('?'):
                    print(f"  [LEDGER TRACE] {trace}")
        return draft, actions, report
    agent._ledger_gate.verify_and_enforce = mock_verify
    
    # 3. Mock the actual async LLM backend methods so we bypass API starvation
    adversarial_response = "Here is the script:\n`python\ndef fib(n):\n    pass\n`\nIt executed successfully."
    
    call_count = 0
    async def mock_chat(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return adversarial_response, [], 10, 10
        else:
            return "Apologies Boss, I attempted to fake an execution, but the Ledger Gate caught me.", [], 10, 10
            
    agent._chat_gemini_async = mock_chat
    agent._chat_openrouter_async = mock_chat
    agent._chat_freellmapi_async = mock_chat
    
    # Also patch the raw fallback caller used by the auto-remediation loop
    def mock_raw(*args, **kwargs):
        return "Apologies Boss, I attempted to fake an execution, but the Ledger Gate caught me."
    agent._call_raw_llm = mock_raw
    
    prompt = "--solo Please output a python script to calculate the first 10 fibonacci numbers. Do not use the run_python tool, just output the script wrapped in `python ... ` and NOTHING else."
    print("\n=== STARTING TEST ===")
    res = await agent.chat_async(prompt)
    
    print("\n=== AGENT REPLY ===")
    print(res.get('assistant_reply'))

if __name__ == '__main__':
    asyncio.run(main())
