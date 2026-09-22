import re
from dataclasses import dataclass

@dataclass
class RoutingDecision:
    model: str
    score: int
    reason: str

class ComplexityRouter:
    def __init__(
        self,
        haiku_model: str,
        sonnet_model: str,
        threshold: int = 5,
        llm_cfg = None,
    ) -> None:
        self.haiku_model = haiku_model
        self.sonnet_model = sonnet_model
        self.threshold = threshold
        self.llm_cfg = llm_cfg

    def route(
        self,
        message: str,
        history_length: int = 0,
        force_model: str | None = None,
    ) -> RoutingDecision:
        # Fallback sync routing if called synchronously
        if force_model:
            return RoutingDecision(model=force_model, score=-1, reason="forced override")
        return RoutingDecision(model=self.haiku_model, score=0, reason="sync fallback")
        
    async def route_async(
        self,
        message: str,
        history_length: int = 0,
        force_model: str | None = None,
    ) -> RoutingDecision:
        if force_model:
            return RoutingDecision(model=force_model, score=-1, reason="forced override")
            
        if not self.llm_cfg or not message.strip():
            return RoutingDecision(model=self.haiku_model, score=0, reason="baseline fallback")
            
        fast_model = self.llm_cfg.gemini_model_lite
        actual_model = fast_model.replace("openrouter/", "") if fast_model.startswith("openrouter/") else fast_model
        
        prompt = f'''You are an ultra-fast request routing AI. 
Evaluate the complexity of this user request:
---
{message[:1000]}
---

If the request is a simple factual question, greeting, short status update, or requires NO deep reasoning, return "SIMPLE".
If the request is complex, requires analysis, coding, long-form writing, planning, or deep reasoning, return "COMPLEX".
Reply with ONLY the word "SIMPLE" or "COMPLEX".'''
        
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": actual_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.0,
                    "max_tokens": 10
                }
                headers = {
                    "Authorization": f"Bearer {self.llm_cfg.openrouter_api_key}",
                    "Content-Type": "application/json"
                }
                async with session.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        content = data["choices"][0]["message"]["content"].strip().upper()
                        if "COMPLEX" in content:
                            return RoutingDecision(model=self.sonnet_model, score=10, reason="LLM Triage: COMPLEX")
                        else:
                            return RoutingDecision(model=self.haiku_model, score=0, reason="LLM Triage: SIMPLE")
                    else:
                        err_text = await resp.text()
                        print(f"  [ROUTER ERROR] API Error {resp.status}: {err_text}")
        except Exception as e:
            print(f"  [ROUTER ERROR] Failed to triage model: {e}")
            
        return RoutingDecision(model=self.sonnet_model, score=5, reason="fallback due to error")
