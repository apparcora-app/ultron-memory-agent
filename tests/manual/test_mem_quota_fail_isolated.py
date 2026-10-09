import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
os.environ["LLM_PROVIDER"] = "google_genai"
os.environ["LLM_MODEL"] = "gemini-1.5-flash"

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agent import MemoryAgent, AgentConfig, LLMConfig

def main():
    agent = MemoryAgent("test_quota_fail_user")
    
    # Mock the internal mem0 add method to simulate the silent drop behavior (e.g. rate limit swallowed by litellm)
    agent._memory.mem.add = lambda **kwargs: {"results": []}
    
    agent._pending_turns = [{"role": "user", "content": "My favorite color is green."}]
    
    try:
        print("Forcing memory flush directly to simulate processing a turn...")
        agent._flush_memory_update()
        print("SUCCESS? This should not print if the error surfaced properly!")
    except Exception as e:
        print(f"BUBBLED UP ERROR: {type(e).__name__} - {e}")

if __name__ == "__main__":
    main()
