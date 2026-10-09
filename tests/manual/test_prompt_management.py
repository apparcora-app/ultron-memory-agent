import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import asyncio
from agent import MemoryAgent
from dotenv import load_dotenv

async def test_prompt_manager():
    print("\n[Layer 8] Initializing Ultron Memory Agent...")
    print("This will check if Langfuse Prompt Management is configured.\n")
    
    # Load environment variables (LANGFUSE keys)
    load_dotenv()
    
    # Initialize the agent
    agent = MemoryAgent()
    
    print("\n--- Triggering Prompt Build ---")
    # This will trigger the _build_system_prompt function and call Langfuse
    sys_prompt, _ = agent._build_system_prompt('hello', '', 'ultron_prime', '', '', '')
    
    print(f"\n[Success] Final System Prompt Length: {len(sys_prompt)} characters")
    print("\n--- Persona Preview (First 300 chars) ---")
    print(sys_prompt[:300])
    print("...\n")

if __name__ == "__main__":
    asyncio.run(test_prompt_manager())
