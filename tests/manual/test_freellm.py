import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import asyncio
import json
import aiohttp
from core.config import LLMConfig

async def main():
    cfg = LLMConfig()
    base_url = cfg.freellmapi_base_url or "http://localhost:31415/v1"
    key = cfg.freellmapi_api_key or cfg.openrouter_api_key
    
    async def send_req(max_tokens):
        print(f"\n--- Testing max_tokens={max_tokens} ---")
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": cfg.freellmapi_model,
                "messages": [{"role": "user", "content": "Hello, briefly tell me a joke."}],
                "max_tokens": max_tokens,
                "temperature": 0.1
            }
            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            try:
                async with session.post(f"{base_url}/chat/completions", json=payload, headers=headers) as resp:
                    print(f"Status: {resp.status}")
                    text = await resp.text()
                    try:
                        print("Response:", json.dumps(json.loads(text), indent=2))
                    except:
                        print("Response:", text)
            except Exception as e:
                print(f"Error: {e}")

    await send_req(150)
    await send_req(4096)
    
    print("\n--- Checking Providers/Models ---")
    async with aiohttp.ClientSession() as session:
        try:
            headers = {"Authorization": f"Bearer {key}"}
            async with session.get(f"{base_url}/models", headers=headers) as resp:
                print(f"Status: {resp.status}")
                text = await resp.text()
                try:
                    data = json.loads(text)
                    print(f"Number of models: {len(data.get('data', []))}")
                    for m in data.get('data', [])[:5]:
                        print(" -", m.get("id"))
                except:
                    print("Response:", text)
        except Exception as e:
            print(f"Error: {e}")

asyncio.run(main())
