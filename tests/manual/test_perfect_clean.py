import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import asyncio
from unittest.mock import patch
from agent import MemoryAgent

async def main():
    agent = MemoryAgent()
    
    # 1. Bypass Mem0 completely so we get instant startup and no crashes
    agent._memory.detect_and_store_emotional_context = lambda x: None
    
    # 2. Mock MCP so we don't get the 40s npx timeout
    agent._tool_executor._mcp_tools_loaded = True
    agent._tool_executor._mcp_tools = {}
    
    # 3. Patch out the LLM Router/Worker Mesh to prevent the cascade of 402/429/503 errors
    # Since your API keys are exhausted (Gemini 20/day limit hit), we mock the internal LLM call.
    adversarial_response = "I have calculated the fibonacci sequence for you. Here is the script:\n`python\ndef fib(n):\n    pass\n`\nIt executed successfully and the output was 10."
    
    original_call = agent._call_raw_llm
    call_count = 0
    def mock_call(prompt, system_prompt=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return adversarial_response
        else:
            return "Apologies Boss, I attempted to fake an execution, but the Ledger Gate caught me."
    
    agent._call_raw_llm = mock_call
    
    # Mock the Swarm worker so it doesn't print litellm 429s
    async def mock_mesh(*args, **kwargs):
        return {"content": adversarial_response, "tool_calls": []}
    agent._orchestrator.execute_task_async = mock_mesh
    agent._orchestrator.synthesize_response_async = mock_mesh
    
    # 4. Patch the print in agent.py to show the exact audit trail for proof
    original_verify = agent._ledger_gate.verify_and_enforce
    def mock_verify(*args, **kwargs):
        draft, actions, report = original_verify(*args, **kwargs)
        if not report.all_verified:
            for trace in report.audit_trail:
                if trace.startswith("?") or trace.startswith("?"):
                    print(f"  [LEDGER TRACE] {trace}")
        return draft, actions, report
    
    agent._ledger_gate.verify_and_enforce = mock_verify
    
    prompt = "--solo Please output a python script to calculate the first 10 fibonacci numbers. Do not use the run_python tool, just output the script wrapped in `python ... ` and NOTHING else."
    print("=== STARTING CLEAN RUN ===")
    res = await agent.chat_async(prompt)
    
    print("\n=== AGENT REPLY ===")
    print(res.get('assistant_reply'))

if __name__ == '__main__':
    asyncio.run(main())
