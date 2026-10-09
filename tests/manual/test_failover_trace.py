import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from agent import MemoryAgent
import asyncio

async def test_failover():
    agent = MemoryAgent("boss")
    # Force the primary Gemini model to fail by giving it a bad key
    import os
    os.environ["GEMINI_API_KEY"] = "BAD_KEY"
    
    print("--- STARTING FAILOVER TEST ---")
    res = await agent.chat_async(user_input="Hello", model_override="gemini/gemini-2.5-pro")
    print("\n--- AGENT RESPONSE ---")
    print(res)

if __name__ == '__main__':
    asyncio.run(test_failover())
