import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import asyncio
import uuid
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from memory.memory_manager import MemoryManager

async def worker(mem_mgr, worker_id, iterations=3):
    for i in range(iterations):
        mem_id = f"test_{worker_id}_{i}_{uuid.uuid4().hex[:8]}"
        try:
            await asyncio.to_thread(
                mem_mgr.add, 
                [{"role": "user", "content": f"Concurrent memory {worker_id} iteration {i}"}]
            )
            print(f"Worker {worker_id} wrote memory {i}")
            
            # Concurrent read
            res = await asyncio.to_thread(mem_mgr.search, "Concurrent memory")
            print(f"Worker {worker_id} read {len(res)} memories")
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
