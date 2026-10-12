import asyncio
import time
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent import MemoryAgent

async def main():
    print("=== ULTRON LATENCY PROFILER ===")
    t0 = time.time()
    print("Step 1: Instantiating MemoryAgent...")
    agent = MemoryAgent(user_id="test_profiler")
    t_init = time.time() - t0
    print(f"MemoryAgent initialized in {t_init:.2f}s")

    prompt = "What is the capital of France?"
    print(f"\nStep 2: Sending test prompt: '{prompt}'...")
    t_chat_start = time.time()
    
    # We will test default parameters
    res = await agent.chat_async(
        user_input=prompt,
        operation_mode="SWARM",
        optimize_prompt=True,
    )
    t_chat_dur = time.time() - t_chat_start
    print("\n=== RESULTS (DEFAULT SWARM MODE + OPTIMIZE PROMPT) ===")
    print(f"Total Response Time: {t_chat_dur:.2f}s")
    print(f"Model Used: {res.get('model_used')}")
    print(f"Model Display: {res.get('model_display')}")
    print(f"Route Reason: {res.get('route_reason')}")
    print(f"Is Swarm: {res.get('is_swarm')}")
    print(f"Skills Used: {len(res.get('skills_used', []))}")
    print(f"Reply: {res.get('reply', '')[:200]}...")

    # Now let's test SOLO mode with optimize_prompt=False to see the difference!
    print("\nStep 3: Sending test prompt in SOLO MODE (optimize_prompt=False)...")
    t_solo_start = time.time()
    res_solo = await agent.chat_async(
        user_input=prompt,
        operation_mode="SOLO",
        optimize_prompt=False,
    )
    t_solo_dur = time.time() - t_solo_start
    # Test Warm Turn in Solo Mode
    print("\nStep 4: Sending follow-up warm query in SOLO MODE...")
    t_warm = time.time()
    res_warm = await agent.chat_async(
        user_input="Tell me three fun facts about it.",
        operation_mode="SOLO",
        optimize_prompt=False,
    )
    t_warm_dur = time.time() - t_warm
    print("\n=== RESULTS (WARM TURN, SOLO MODE) ===")
    print(f"Total Response Time: {t_warm_dur:.2f}s")
    print(f"Reply: {res_warm.get('reply', '')[:200]}...")

if __name__ == "__main__":
    asyncio.run(main())
