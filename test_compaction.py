import asyncio
import sys
sys.stdout.reconfigure(encoding='utf-8')
from tool_definitions import ToolExecutor

async def main():
    executor = ToolExecutor()
    print("Testing Tool Output Compaction (EXPECT: Intercepted and written to data/scratch/...)")
    
    # We use execute_command with a command that produces a lot of output
    res = await executor.execute_async("execute_command", {"command": 'dir "C:\Program Files" /s'})
    
    print(f"\nResult Length (Compacted): {len(res['output'])}")
    print("--- Output Snippet ---")
    print(res['output'])

if __name__ == '__main__':
    asyncio.run(main())
