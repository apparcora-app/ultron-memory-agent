"""
tests/test_tool_cache.py — Tool output caching and bypass verification.
"""
import sys
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import os
import asyncio
from tool_definitions import ToolExecutor


async def _run_test():
    executor = ToolExecutor()
    print("Test 1: web_search for 'Ultron Protocol' (EXPECT: CACHE MISS)")
    res1 = await executor.execute_async("web_search", {"query": "Ultron Protocol", "num_results": 1})
    print(f"Result length: {len(res1['output'])}")

    print("\nTest 2: Exact same web_search (EXPECT: CACHE HIT)")
    res2 = await executor.execute_async("web_search", {"query": "Ultron Protocol", "num_results": 1})
    print(f"Result length: {len(res2['output'])}")
    print(f"Duration MS for hit: {res2.get('duration_ms', 0)}")

    print("\nTest 3: Different web_search (EXPECT: CACHE MISS)")
    res3 = await executor.execute_async("web_search", {"query": "Artificial Intelligence", "num_results": 1})
    print(f"Result length: {len(res3['output'])}")

    scratch_path = os.path.join("data", "scratch", "test_cache.txt")
    os.makedirs(os.path.dirname(scratch_path), exist_ok=True)

    print("\nTest 4: Mutating file_operation (EXPECT: bypass cache, no cache logs)")
    res4 = await executor.execute_async("file_operation", {"operation": "write", "path": scratch_path, "content": "hello"})
    print(f"Result: {res4['output']}")

    print("\nTest 5: Read file_operation (EXPECT: CACHE MISS)")
    res5 = await executor.execute_async("file_operation", {"operation": "read", "path": scratch_path})
    print(f"Result: {res5['output']}")

    print("\nTest 6: Exact same Read file_operation (EXPECT: CACHE HIT)")
    res6 = await executor.execute_async("file_operation", {"operation": "read", "path": scratch_path})
    print(f"Result: {res6['output']}")

    # Cleanup temporary file
    if os.path.exists(scratch_path):
        try:
            os.remove(scratch_path)
        except OSError:
            pass


def test_tool_cache():
    asyncio.run(_run_test())


if __name__ == '__main__':
    asyncio.run(_run_test())
