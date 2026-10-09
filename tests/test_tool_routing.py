"""
tests/test_tool_routing.py — Dynamic tool triage and MCP routing test.
"""
import sys
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import asyncio
from core.config import LLMConfig
from mcp_client import MCPManager
from core.tool_router import DynamicToolRouter


async def _run_test():
    cfg = LLMConfig()
    mcp = MCPManager()
    router = DynamicToolRouter(cfg)
    
    intent_1 = "Please search the web for the latest weather in Tokyo."
    intent_2 = "Can you check my git log and list my recent commits?"
    
    print("\n" + "=" * 50)
    print("--- TEST 1: WEB SEARCH INTENT ---")
    print(f"User Input: {intent_1}")
    from core.tool_definitions import ULTRON_TOOLS
    print(f"DEBUG IN TEST: len(ULTRON_TOOLS)={len(ULTRON_TOOLS)}")
    tools_1 = await router.route_tools(intent_1, mcp)
    print(f"\nFinal Tool Count: {len(tools_1)}")
    print(f"Included Tool Names: {[t['name'] for t in tools_1]}")
    assert len(tools_1) > 0
    
    print("\n" + "=" * 50)
    print("--- TEST 2: GITHUB INTENT ---")
    print(f"User Input: {intent_2}")
    tools_2 = await router.route_tools(intent_2, mcp)
    print(f"\nFinal Tool Count: {len(tools_2)}")
    print(f"Included Tool Names: {[t['name'] for t in tools_2]}")
    print("=" * 50 + "\n")
    assert len(tools_2) > 0


def test_tool_routing():
    asyncio.run(_run_test())


if __name__ == "__main__":
    asyncio.run(_run_test())
