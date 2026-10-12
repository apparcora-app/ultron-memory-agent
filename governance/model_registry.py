"""
governance/model_registry.py — Centralized Model Registry & Rotation Pool Engine.

Provides:
  1. Centralized model catalog, provider mappings, and capability tiers.
  2. Dynamic candidate rotation pools for Gemini, OpenRouter, and Anthropic.
  3. Circuit-breaker awareness: automatically filters out providers/models whose
     circuit breaker state is currently OPEN to prevent wasted latency.
  4. Single source of truth for fallback sequences, eliminating duplicated hardcoded lists.
"""

from __future__ import annotations

import enum

from pydantic import BaseModel, ConfigDict

from core.log_config import get_logger
from resilience.circuit_breaker import default_breaker_registry


class ModelProvider(str, enum.Enum):
    GEMINI = "gemini"
    OPENROUTER = "openrouter"
    ANTHROPIC = "anthropic"
    FREELLMAPI = "freellmapi"
    LOCAL = "local"


class ModelTier(str, enum.Enum):
    FAST = "fast"
    STANDARD = "standard"
    REASONING = "reasoning"
    EMBEDDING = "embedding"


class ModelSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    model_id: str
    provider: ModelProvider
    tier: ModelTier
    max_output_tokens: int = 8192
    temperature: float = 0.2
    supports_vision: bool = True
    supports_tools: bool = True
    context_window: int = 128_000


# ── Canonical Candidate Rotation Pools ─────────────────────────────────────────

DEFAULT_FREELLMAPI_MODEL = 'gpt-oss-120b'

DEFAULT_ROTATION_POOLS: dict[str, list[str]] = {
    "gemini": [
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "gemini-3.1-pro-preview",
        # Forward compatibility aliases
        "gemini-3.6-flash",
        "gemini-3.6-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
    ],
    "openrouter": [
        "deepseek/deepseek-chat",
        "openai/gpt-4o-mini",
        "anthropic/claude-3.5-haiku",
        "google/gemini-2.0-flash-001",
    ],
    "anthropic": [
        "claude-3-7-sonnet-20250219",
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
    ],
    "freellmapi": [
        "auto",
        "groq/llama-3.3-70b-versatile",
        "cerebras/llama3.1-8b",
        "gemini-2.0-flash",
        "mistral/mistral-small",
        "cloudflare/@cf/meta/llama-3.1-8b-instruct",
        "nvidia/meta/llama-3.1-70b-instruct",
    ],
}


class ModelRegistry:
    """
    Centralized registry managing LLM models, provider selection, and resilient candidate pools.
    """

    def __init__(self, rotation_pools: dict[str, list[str]] | None = None) -> None:
        self._rotation_pools: dict[str, list[str]] = dict(rotation_pools or DEFAULT_ROTATION_POOLS)

    def get_candidate_pool(
        self,
        provider: str = "gemini",
        preferred_model: str | None = None,
        filter_open_circuit: bool = True,
    ) -> list[str]:
        """
        Returns an ordered, deduplicated candidate model rotation pool for the specified provider.
        If preferred_model is given, it is placed at the front of the candidate sequence.
        If filter_open_circuit is True, models whose circuit breaker is OPEN are omitted.
        """
        base_pool = list(self._rotation_pools.get(provider.lower(), []))

        candidates: list[str] = []
        if preferred_model:
            candidates.append(preferred_model)
        for m in base_pool:
            if m not in candidates:
                candidates.append(m)

        if not filter_open_circuit:
            return candidates

        # Filter out models whose circuit breaker is currently OPEN
        healthy_candidates: list[str] = []
        for model in candidates:
            breaker = default_breaker_registry.get_breaker(f"{provider}_{model}") or default_breaker_registry.get_breaker(model)
            if breaker is not None:
                state_val = breaker.state.value if hasattr(breaker.state, "value") else str(breaker.state)
                if state_val == "OPEN":
                    continue
            healthy_candidates.append(model)

        # Fallback to candidates if all breakers are open to allow probe trials
        return healthy_candidates if healthy_candidates else candidates

    def register_candidate_pool(self, provider: str, models: list[str]) -> None:
        """Dynamically registers or overrides a provider's model pool."""
        self._rotation_pools[provider.lower()] = list(dict.fromkeys(models))

    def list_providers(self) -> list[str]:
        """Returns all configured provider keys."""
        return list(self._rotation_pools.keys())


# Global default model registry instance
default_model_registry = ModelRegistry()


_log = get_logger('model_registry')
