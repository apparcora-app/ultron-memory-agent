from dataclasses import dataclass

from core.log_config import get_logger


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
        fast_model.replace("openrouter/", "") if fast_model.startswith("openrouter/") else fast_model

        prompt = f'''You are an ultra-fast request routing AI.
Evaluate the complexity of this user request:
---
{message[:1000]}
---

If the request is a simple factual question, greeting, short status update, or requires NO deep reasoning, return "SIMPLE".
If the request is complex, requires analysis, coding, long-form writing, planning, or deep reasoning, return "COMPLEX".
Reply with ONLY the word "SIMPLE" or "COMPLEX".'''

        try:
            from core.llm_chain import chat_with_fallback
            content, _, _ = await chat_with_fallback(prompt, "", max_tokens=10, model_override=fast_model)
            if "COMPLEX" in content.upper():
                return RoutingDecision(model=self.sonnet_model, score=10, reason="LLM Triage: COMPLEX")
            else:
                return RoutingDecision(model=self.haiku_model, score=0, reason="LLM Triage: SIMPLE")
        except Exception as e:
            _log.error(f"  [ROUTER ERROR] Failed to triage model: {e}")

        return RoutingDecision(model=self.sonnet_model, score=5, reason="fallback due to error")

_log = get_logger('model_router')
