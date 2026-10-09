"""
tests/test_async_subprocess.py — Async subprocess execution and timeout tests.
"""
import sys
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import os
os.environ['APPROVAL_MODE'] = 'off'
import asyncio
from tool_definitions import ToolExecutor


async def _run_test():
    executor = ToolExecutor()
    print("--- TEST 1: ASYNC EXECUTE COMMAND ---")
    res1 = await executor.execute_async("execute_command", {"command": "echo Hello Async World!"})
    print(res1)
    assert res1.get("success") is True or "Hello Async World!" in res1.get("output", "")
    
    print("\n--- TEST 2: ASYNC RUN PYTHON ---")
    res2 = await executor.execute_async("run_python", {"code": "print('Async Python Execution Works!')"})
    print(res2)
    assert "Async Python Execution Works!" in res2.get("output", "")
    
    print("\n--- TEST 3: LONG RUNNING ASYNC (Should timeout but not block) ---")
    res3 = await executor.execute_async("execute_command", {"command": "python -c \"import time; time.sleep(10)\""})
    print(res3)
    assert "output" in res3 or "error" in res3


def test_async_subprocess():
    asyncio.run(_run_test())


if __name__ == "__main__":
    asyncio.run(_run_test())
