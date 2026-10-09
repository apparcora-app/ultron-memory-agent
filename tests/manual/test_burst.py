import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import asyncio
import httpx
import time

async def fetch(client, key, idx):
    headers = {"X-API-Key": key}
    resp = await client.get("http://127.0.0.1:8000/api/providers", headers=headers)
    return resp.status_code

async def test_keys_concurrent(key1, key2):
    async with httpx.AsyncClient() as client:
        print(f"--- Bursting concurrently ---")
        tasks1 = [fetch(client, key1, i) for i in range(120)]
        tasks2 = [fetch(client, key2, i) for i in range(20)]
        
        res = await asyncio.gather(*(tasks1 + tasks2))
        res1 = res[:120]
        res2 = res[120:]
        print(f"Key 1 (limit 60): 200={res1.count(200)}, 429={res1.count(429)}, 401={res1.count(401)}")
        print(f"Key 2 (20 reqs): 200={res2.count(200)}, 429={res2.count(429)}, 401={res2.count(401)}")

async def main():
    keys = [k.strip() for k in os.environ.get("API_KEYS", "").split(",") if k.strip()]
    k1 = os.environ.get("ULTRON_TEST_KEY_1") or (keys[0] if keys else "test-burst-key-1")
    k2 = os.environ.get("ULTRON_TEST_KEY_2") or (keys[1] if len(keys) > 1 else "test-burst-key-2")
    await test_keys_concurrent(k1, k2)

if __name__ == "__main__":
    asyncio.run(main())
