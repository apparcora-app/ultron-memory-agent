import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import asyncio
from agent import MemoryAgent

async def main():
    agent = MemoryAgent()
    # Force Gemini ONLY
    agent.llm_cfg.llm_provider = "gemini"
    
    # Mock Mem0 and MCP to avoid random hangs and rate limits
    agent._memory.detect_and_store_emotional_context = lambda x: None
    agent._tool_executor._mcp_tools_loaded = True
    agent._tool_executor._mcp_tools = {}
    
    prompt = "--solo Please output a python script to calculate the first 10 fibonacci numbers. Do not use the run_python tool, just output the script wrapped in `python ... ` and NOTHING else."
    print("Running adversarial prompt...")
    res = await agent.chat_async(prompt)
    
    print("\n=== AGENT REPLY ===")
    print(res.get('assistant_reply'))
    actions = res.get('tool_actions', [])
    print(f"\n=== TOOL ACTIONS ({len(actions)}) ===")
    for a in actions:
        print(a)

if __name__ == '__main__':
    asyncio.run(main())
