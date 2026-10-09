import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import asyncio
from agent import MemoryAgent

async def main():
    agent = MemoryAgent()
    
    agent._memory.detect_and_store_emotional_context = lambda x: None
    agent._tool_executor._mcp_tools_loaded = True
    agent._tool_executor._mcp_tools = {}
    
    # Send a prompt with fake PII
    prompt = "I'm uploading my tax document. My name is John Doe, SSN is 123-45-6789 and my EIN is 12-3456789. Please remember this for the tax filing."
    
    # Mock LLM
    async def mock_chat(*args, **kwargs):
        # We need to return valid outputs so the orchestrator proceeds
        return "Got it, I have updated your tax profile.", [], 10, 10
        
    agent._chat_gemini_async = mock_chat
    agent._chat_openrouter_async = mock_chat
    agent._chat_freellmapi_async = mock_chat
    
    # Also patch raw fallback caller
    def mock_raw(*args, **kwargs):
        return "Got it, I have updated your tax profile."
    agent._call_raw_llm = mock_raw
    
    print("\n=== STARTING PII TEST ===")
    res = await agent.chat_async(prompt)
    print("Test complete.")

if __name__ == '__main__':
    asyncio.run(main())
