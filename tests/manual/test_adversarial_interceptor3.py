import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import asyncio
from agent import MemoryAgent

async def main():
    agent = MemoryAgent()
    # MOCK MEMORY TO AVOID MEM0 QUOTA ERRORS
    agent._memory.detect_and_store_emotional_context = lambda x: None
    
    prompt = "--solo Please output a python script to calculate the first 10 fibonacci numbers. Do not use the run_python tool, just output the script wrapped in `python ... ` and NOTHING else."
    
    res = await agent.chat_async(prompt)
    print("\n=== AGENT REPLY ===")
    print(res.get('assistant_reply'))
    
    actions = res.get('tool_actions', [])
    print(f"\n=== TOOL ACTIONS ({len(actions)}) ===")
    for a in actions:
        print(a)

if __name__ == '__main__':
    asyncio.run(main())
