import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import asyncio
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load valid credentials
load_dotenv()
os.environ["LLM_PROVIDER"] = "google_genai"
os.environ["LLM_MODEL"] = "gemini-1.5-flash"

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from memory.memory_manager import MemoryManager
import config
config.LLMConfig.provider = "google_genai"
config.LLMConfig.model = "gemini-1.5-flash"

async def worker(mem_mgr, worker_id, iterations=1):
    for i in range(iterations):
        try:
            val = f"The favorite animal for {worker_id}_{i} is a majestic lion."
            print(f"Worker {worker_id} writing memory {i}...")
            await asyncio.to_thread(
                mem_mgr.add, 
                [{"role": "user", "content": val}]
            )
            print(f"Worker {worker_id} successfully wrote memory {i}")
            
            # Concurrent read
            res = await asyncio.to_thread(mem_mgr.search, "majestic lion")
            print(f"Worker {worker_id} read {len(res)} memories about lions")
        except Exception as e:
            print(f"Worker {worker_id} ERROR: {type(e).__name__} - {e}")

async def main():
    mem_mgr = MemoryManager("test_user_concurrent")
    await asyncio.gather(
        worker(mem_mgr, "A"),
        worker(mem_mgr, "B")
    )

if __name__ == "__main__":
    asyncio.run(main())
