import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import asyncio
import os
import httpx
from core.llm_chain import chat_with_fallback

async def main():
    print("=== Case A: Normal call served by FreeLLMAPI ===")
    try:
        content, _, provider = await chat_with_fallback("Hello!", "")
        print(f"Content: {content[:50]}...")
        print(f"Provider: {provider}")
    except Exception as e:
        print(f"Failed: {e}")

    # Case B: Block FreeLLMAPI
    os.environ['FREELLMAPI_BASE_URL'] = "http://localhost:9999/v1" # wrong port
    print("\n=== Case B: FreeLLMAPI blocked goes to OpenRouter ===")
    try:
        content, _, provider = await chat_with_fallback("Hello!", "")
        print(f"Content: {content[:50]}...")
        print(f"Provider: {provider}")
    except Exception as e:
        print(f"Failed: {e}")
    
    # Case C: Block OpenRouter too
    os.environ['OPENROUTER_API_KEY'] = "sk-or-v1-invalid_key"
    print("\n=== Case C: FreeLLMAPI and OpenRouter blocked goes to Gemini ===")
    try:
        content, _, provider = await chat_with_fallback("Hello!", "")
        print(f"Content: {content[:50]}...")
        print(f"Provider: {provider}")
    except Exception as e:
        print(f"Failed: {e}")
    
    # Case D: Block Gemini too
    os.environ['GEMINI_API_KEY'] = "invalid_gemini"
    import core.llm_chain
    from google import genai
    core.llm_chain.gemini_client = genai.Client(api_key="invalid_gemini", http_options={'timeout': 2.0})
    print("\n=== Case D: All three blocked gives a clear error ===")
    try:
        content, _, provider = await chat_with_fallback("Hello!", "")
        print(f"Content: {content[:50]}...")
        print(f"Provider: {provider}")
    except Exception as e:
        print(f"Exception caught: {e}")

asyncio.run(main())
