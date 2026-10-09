import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import asyncio
from core.llm_chain import chat_with_fallback

async def main():
    print("Testing default (client_data=True) -> Should skip FreeLLMAPI:")
    try:
        await chat_with_fallback("Hello")
    except Exception as e:
        print(f"Exception: {e}")

    print("\nTesting opt-out (client_data=False) -> Should attempt FreeLLMAPI:")
    try:
        await chat_with_fallback("Hello", client_data=False)
    except Exception as e:
        print(f"Exception: {e}")

asyncio.run(main())
