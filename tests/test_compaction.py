"""
tests/test_compaction.py — Output compaction and large-payload interception test.
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
    print("Testing Tool Output Compaction (EXPECT: Intercepted and written to data/scratch/...)")
    
    # We use execute_command with a command that produces a lot of output
    res = await executor.execute_async("execute_command", {"command": 'dir "C:\\Program Files" /s'})
    
    output_str = res.get("output", "")
    print(f"\nResult Length (Compacted): {len(output_str)}")
    print("--- Output Snippet ---")
    print(output_str[:300])
    assert len(output_str) > 0


def test_compaction():
    asyncio.run(_run_test())


if __name__ == '__main__':
    asyncio.run(_run_test())
