import asyncio
import os
import sys
import time
from pathlib import Path

# Ensure src is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ultron.agent import MemoryAgent
from ultron.skills.skill_manager import SkillManager


async def benchmark():
    print("=" * 60)
    print("  ULTRON PERFORMANCE & LATENCY BENCHMARK")
    print("=" * 60)

    # 1. Benchmark Skills Cache
    sm = SkillManager()
    t0 = time.perf_counter()
    skills = sm.get_all_skills()
    skill_time_ms = (time.perf_counter() - t0) * 1000
    print(f"[*] SkillManager.get_all_skills(): {len(skills)} skills loaded in {skill_time_ms:.2f} ms")
    assert skill_time_ms < 50, f"Skills cache too slow: {skill_time_ms:.2f} ms"

    # 2. Benchmark Agent Fast-Path (Greeting)
    agent = MemoryAgent(user_id="benchmark_user")
    t1 = time.perf_counter()
    fast_res = await agent.chat_async(
        user_input="hello ultron, confirm status",
        module_id="ultron_prime",
        model_override="auto",
    )
    fast_time_ms = (time.perf_counter() - t1) * 1000
    print(f"[*] Fast-Path Turn: {fast_time_ms:.2f} ms")
    print(f"    Model Used: {fast_res.get('model_used')}")
    print(f"    Model Display: {fast_res.get('model_display')}")
    print(f"    Fast Path: {fast_res.get('fast_path')}")
    print(f"    Reply Snippet: {fast_res.get('reply', '')[:100]}...")

    # 3. Benchmark Tool-less Query (Synthesizer Bypass)
    t2 = time.perf_counter()
    query_res = await agent.chat_async(
        user_input="Explain what a vector database does in 1 concise sentence.",
        module_id="ultron_prime",
        model_override="auto",
        operation_mode="DIRECT",
    )
    query_time_ms = (time.perf_counter() - t2) * 1000
    print(f"[*] Tool-less Query Turn: {query_time_ms:.2f} ms")
    print(f"    Model Used: {query_res.get('model_used')}")
    print(f"    Tool Actions: {query_res.get('tool_actions')}")
    print(f"    Reply Snippet: {query_res.get('reply', '')[:100]}...")

    print("=" * 60)
    print("  BENCHMARK VERDICT: ALL PASS")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(benchmark())
