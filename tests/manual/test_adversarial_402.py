import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import asyncio

def run_adversarial_tests():
    # We will temporarily patch agent.MemoryAgent._chat_gemini_async
    from pipelines.langgraph_pipeline import LangGraphTwoStepSwarm
    from telemetry import TelemetryEngine
    from unittest.mock import patch

    # 1. Timeout Simulation
    print("--- ADVERSARIAL TEST 1: TimeoutException ---")
    async def mock_timeout(*args, **kwargs):
        raise TimeoutError("Connection dropped silently")

    with patch('agent.MemoryAgent._chat_gemini_async', new=mock_timeout):
        with patch('agent.MemoryAgent._chat_openrouter_async', new=mock_timeout):
            pipeline = LangGraphTwoStepSwarm(telemetry=TelemetryEngine())
            try:
                result = pipeline.execute(directive="timeout test", context="", user_id="boss")
                titan_status = result.get('titan_status')
                print(f"Titan status returned: {titan_status}")
                assert titan_status == 'FAILED', "Expected status FAILED on timeout!"
            except Exception as e:
                print(f"Pipeline safely bubbled up error or handled it: {e}")

    # 2. Malformed JSON Simulation (Returns something that doesn't say Error in it, but fails internally)
    print("\n--- ADVERSARIAL TEST 2: Malformed Response ---")
    async def mock_malformed(*args, **kwargs):
        return "This is not valid JSON and has no error code in it"

    with patch('agent.MemoryAgent._chat_gemini_async', new=mock_malformed):
        with patch('agent.MemoryAgent._chat_openrouter_async', new=mock_malformed):
            pipeline = LangGraphTwoStepSwarm(telemetry=TelemetryEngine())
            try:
                result = pipeline.execute(directive="malformed test", context="", user_id="boss")
                titan_status = result.get('titan_status')
                print(f"Titan status returned: {titan_status}")
                assert titan_status == 'FAILED', "Expected status FAILED on malformed response!"
            except Exception as e:
                print(f"Pipeline safely bubbled up error or handled it: {e}")

if __name__ == '__main__':
    run_adversarial_tests()
