import asyncio
from config import LLMConfig
from mcp_client import MCPManager
from tool_router import DynamicToolRouter

async def test():
    cfg = LLMConfig()
    mcp = MCPManager()
    router = DynamicToolRouter(cfg)
    
    intent_1 = "Please search the web for the latest weather in Tokyo."
    intent_2 = "Can you check my git log and list my recent commits?"
    
    print("\n" + "="*50)
    print("--- TEST 1: WEB SEARCH INTENT ---")
    print(f"User Input: {intent_1}")
    tools_1 = await router.route_tools(intent_1, mcp)
    print(f"\nFinal Tool Count: {len(tools_1)}")
    print(f"Included Tool Names: {[t['name'] for t in tools_1]}")
    
    print("\n" + "="*50)
    print("--- TEST 2: GITHUB INTENT ---")
    print(f"User Input: {intent_2}")
    tools_2 = await router.route_tools(intent_2, mcp)
    print(f"\nFinal Tool Count: {len(tools_2)}")
    print(f"Included Tool Names: {[t['name'] for t in tools_2]}")
    print("="*50 + "\n")

asyncio.run(test())
