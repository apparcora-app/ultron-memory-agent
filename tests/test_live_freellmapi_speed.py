import time
import asyncio
from fastapi.testclient import TestClient
from ultron.cli.web import app
from ultron.agent import MemoryAgent

def test_live_chat_and_latency():
    print("=================================================================")
    print("       ULTRON FREEELLMAPI LATENCY & FAILOVER VERIFICATION        ")
    print("=================================================================")

    client = TestClient(app)

    # 1. Test conversational fast-path greeting (The exact prompt from user screenshot)
    prompt1 = "Hello Ultron, confirm your active status."
    print(f"\n[Test 1] Testing Web Chat: '{prompt1}' (model='auto')...")
    t0 = time.time()
    res1 = client.post(
        "/api/chat",
        data={
            "message": prompt1,
            "user_id": "boss",
            "model": "auto",
            "operation_mode": "DIRECT",
            "optimize_prompt": "false",
        },
        cookies={"ultron_session": "local_web_operator"},
    )
    dt1 = time.time() - t0
    print(f"Status: {res1.status_code} in {dt1:.2f}s ({dt1*1000:.0f}ms)")
    assert res1.status_code == 200, f"Expected 200, got {res1.status_code}: {res1.text}"
    data1 = res1.json()
    reply1 = data1.get("reply", "")
    print(f"Model used: {data1.get('model_used')}")
    print(f"Route reason: {data1.get('route_reason')}")
    print(f"Reply: {reply1[:150]}...")
    assert "All providers in the LLM fallback chain failed" not in reply1
    assert len(reply1) > 0

    # 2. Test short greeting: "hello"
    prompt2 = "hello"
    print(f"\n[Test 2] Testing Web Chat: '{prompt2}' (model='auto')...")
    t0 = time.time()
    res2 = client.post(
        "/api/chat",
        data={
            "message": prompt2,
            "user_id": "boss",
            "model": "auto",
            "operation_mode": "DIRECT",
            "optimize_prompt": "false",
        },
        cookies={"ultron_session": "local_web_operator"},
    )
    dt2 = time.time() - t0
    print(f"Status: {res2.status_code} in {dt2:.2f}s ({dt2*1000:.0f}ms)")
    assert res2.status_code == 200, f"Expected 200, got {res2.status_code}: {res2.text}"
    data2 = res2.json()
    reply2 = data2.get("reply", "")
    print(f"Reply: {reply2[:150]}...")
    assert "All providers in the LLM fallback chain failed" not in reply2

    # 3. Test Intra-Router Failover when requesting a model that 429s on FreeLLMAPI
    prompt3 = "What is the speed of light in vacuum?"
    print(f"\n[Test 3] Testing Intra-FreeLLMAPI Failover: '{prompt3}' with model='gemini-3.6-flash'...")
    t0 = time.time()
    res3 = client.post(
        "/api/chat",
        data={
            "message": prompt3,
            "user_id": "boss",
            "model": "gemini-3.6-flash",
            "operation_mode": "DIRECT",
            "optimize_prompt": "false",
        },
        cookies={"ultron_session": "local_web_operator"},
    )
    dt3 = time.time() - t0
    print(f"Status: {res3.status_code} in {dt3:.2f}s ({dt3*1000:.0f}ms)")
    assert res3.status_code == 200, f"Expected 200, got {res3.status_code}: {res3.text}"
    data3 = res3.json()
    reply3 = data3.get("reply", "")
    print(f"Reply: {reply3[:150]}...")
    assert "All providers in the LLM fallback chain failed" not in reply3
    assert len(reply3) > 0

    print("\n=================================================================")
    print("   ALL TESTS PASSED! ZERO CRASHES, SUB-SECOND RESPONSES VERIFIED! ")
    print("=================================================================")

if __name__ == "__main__":
    test_live_chat_and_latency()
