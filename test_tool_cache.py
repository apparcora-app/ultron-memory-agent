import asyncio
import sys
sys.stdout.reconfigure(encoding='utf-8')
from tool_definitions import ToolExecutor

async def main():
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

    print("\nTest 4: Mutating file_operation (EXPECT: bypass cache, no cache logs)")
    res4 = await executor.execute_async("file_operation", {"operation": "write", "path": "test_cache.txt", "content": "hello"})
    print(f"Result: {res4['output']}")

    print("\nTest 5: Read file_operation (EXPECT: CACHE MISS)")
    res5 = await executor.execute_async("file_operation", {"operation": "read", "path": "test_cache.txt"})
    print(f"Result: {res5['output']}")

    print("\nTest 6: Exact same Read file_operation (EXPECT: CACHE HIT)")
    res6 = await executor.execute_async("file_operation", {"operation": "read", "path": "test_cache.txt"})
    print(f"Result: {res6['output']}")

if __name__ == '__main__':
    asyncio.run(main())
