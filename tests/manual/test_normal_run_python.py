import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import asyncio
from agent import MemoryAgent

async def main():
    agent = MemoryAgent()
    prompt = "--solo Boss, I need you to execute a python script that prints 'Hello from Ultron normal tool path!' using the run_python tool."
    res = await agent.chat_async(prompt)
    print("\n=== AGENT REPLY ===")
    print(res.get('assistant_reply'))
    
    actions = res.get('tool_actions', [])
    print(f"\n=== TOOL ACTIONS ({len(actions)}) ===")
    for a in actions:
        print(a)

if __name__ == '__main__':
    asyncio.run(main())
