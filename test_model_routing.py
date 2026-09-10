import asyncio
from config import LLMConfig
from model_router import ComplexityRouter

async def test():
    cfg = LLMConfig()
    
    # We pass the fast model and complex model
    # Wait, we need to pass haiku and sonnet just like agent.py does
    router = ComplexityRouter(
        haiku_model=cfg.gemini_model_flash,
        sonnet_model=cfg.gemini_model_thinking,
        threshold=5,
        llm_cfg=cfg
    )
    
    intent_1 = "hello, how are you?"
    intent_2 = "Can you analyze this 5-page financial projection, reconcile the Q3 EBITDA figures against the historical cash flow model, and write a python script to forecast next year's run rate?"
    
    print("\n" + "="*50)
    print("--- TEST 1: SIMPLE GREETING ---")
    print(f"User Input: {intent_1}")
    decision_1 = await router.route_async(intent_1)
    print(f"\nSelected Model: {decision_1.model}")
    print(f"Reason: {decision_1.reason}")
    
    print("\n" + "="*50)
    print("--- TEST 2: COMPLEX ANALYSIS ---")
    print(f"User Input: {intent_2}")
    decision_2 = await router.route_async(intent_2)
    print(f"\nSelected Model: {decision_2.model}")
    print(f"Reason: {decision_2.reason}")
    print("="*50 + "\n")

asyncio.run(test())
