"""
tests/evals/test_agent_hallucination.py - Layer 7: Evaluation & Testing

Automated LLM Evaluation using DeepEval.
This script tests the agent's logic and hallucination rates.

To run:
  pytest tests/evals/test_agent_hallucination.py
"""

import pytest
import os
import sys
import time
import urllib.request
import subprocess
import asyncio

try:
    from deepeval import assert_test
    from deepeval.test_case import LLMTestCase
    from deepeval.metrics import HallucinationMetric, AnswerRelevancyMetric
    DEEPEVAL_AVAILABLE = True
except ImportError:
    DEEPEVAL_AVAILABLE = False

from agent import MemoryAgent

# DeepEval evaluation tasks operate on public synthetic benchmarks and contain zero confidential client data.
# client_data is explicitly set to False to permit routing through FreeLLMAPI for evaluation runs.
DEEPEVAL_CLIENT_DATA: bool = False


@pytest.fixture(scope="session", autouse=True)
def run_local_endpoint():
    """
    Session-scoped fixture to automatically start local_endpoint.py on port 31416
    and ensure clean teardown when tests complete.
    """
    proc = None
    endpoint_alive = False
    
    # Check if local_endpoint is already responding on 31416
    try:
        req = urllib.request.Request("http://127.0.0.1:31416/health")
        with urllib.request.urlopen(req, timeout=1) as resp:
            if resp.status == 200:
                endpoint_alive = True
    except Exception:
        endpoint_alive = False

    if not endpoint_alive:
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        proc = subprocess.Popen(
            [sys.executable, "local_endpoint.py"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=root_dir
        )
        
        # Wait up to 15 seconds for endpoint to become ready
        for _ in range(30):
            try:
                req = urllib.request.Request("http://127.0.0.1:31416/health")
                with urllib.request.urlopen(req, timeout=1) as resp:
                    if resp.status == 200:
                        endpoint_alive = True
                        break
            except Exception:
                if proc.poll() is not None:
                    break
                time.sleep(0.5)

    os.environ['OPENAI_BASE_URL'] = 'http://127.0.0.1:31416/v1'
    os.environ['OPENAI_API_KEY'] = 'sk-dummy'

    yield

    # Clean teardown: stop spawned process
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.mark.asyncio
@pytest.mark.llm_live
@pytest.mark.skipif(not DEEPEVAL_AVAILABLE, reason="deepeval is not installed")
async def test_agent_factual_accuracy():
    """
    Tests if the agent hallucinates when asked a direct factual question,
    and whether its answer is relevant to the prompt.
    """
    # 1. Initialize Agent
    agent = MemoryAgent(user_id="test_evals_user_unique")
    
    # 2. Run the actual agent query with explicit client_data constant
    input_text = "What is the capital of France, and what is its most famous tower?"
    response = await agent.chat_async(input_text, model_override="freellmapi", client_data=DEEPEVAL_CLIENT_DATA)
    
    if "reply" not in response:
        pytest.fail(f"LLM Error: {response}")
    actual_output = response["reply"]
    
    # 3. Define the evaluation case
    test_case = LLMTestCase(
        input=input_text,
        actual_output=actual_output,
        context=["The capital of France is Paris. Its most famous tower is the Eiffel Tower."]
    )
    
    # 4. Define Metrics
    hallucination_metric = HallucinationMetric(threshold=0.5)
    relevancy_metric = AnswerRelevancyMetric(threshold=0.5)
    
    # 5. Run the assertion
    assert_test(test_case, [hallucination_metric, relevancy_metric])


@pytest.mark.asyncio
@pytest.mark.llm_live
@pytest.mark.skipif(not DEEPEVAL_AVAILABLE, reason="deepeval is not installed")
async def test_agent_tool_relevancy():
    """
    Tests if the agent's decision to use a tool makes sense given the context.
    """
    agent = MemoryAgent(user_id="test_evals_user_unique")
    
    input_text = "Search the web for the latest news about OpenAI."
    response = await agent.chat_async(input_text, model_override="freellmapi", client_data=DEEPEVAL_CLIENT_DATA)
    
    if "reply" not in response:
        pytest.fail(f"LLM Error: {response}")
    actual_output = response["reply"]
    
    test_case = LLMTestCase(
        input=input_text,
        actual_output=actual_output,
        context=["The user asked for web search. The agent should utilize a search tool or state the search results."]
    )
    
    relevancy_metric = AnswerRelevancyMetric(threshold=0.5)
    assert_test(test_case, [relevancy_metric])
