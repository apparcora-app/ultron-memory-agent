import asyncio
from tool_definitions import ToolExecutor

async def test():
    executor = ToolExecutor()
    print("--- TEST 1: ASYNC EXECUTE COMMAND ---")
    res1 = await executor.execute_async("execute_command", {"command": "echo Hello Async World!"})
    print(res1)
    
    print("\n--- TEST 2: ASYNC RUN PYTHON ---")
    res2 = await executor.execute_async("run_python", {"code": "print('Async Python Execution Works!')"})
    print(res2)
    
    # Also verify time out works without blocking
    print("\n--- TEST 3: LONG RUNNING ASYNC (Should timeout but not block) ---")
    res3 = await executor.execute_async("execute_command", {"command": "python -c \"import time; time.sleep(10)\""})
    print(res3)

asyncio.run(test())
