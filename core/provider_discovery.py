"""
core/provider_discovery.py — API Key → Model List Discovery Engine

Paste any API key → instantly see every model available on that provider,
with free/paid badge, context window, tier classification, and one-command
add to providers.yaml.

Supported providers:
  - OpenRouter  (300+ models: Gemini, DeepSeek, NVIDIA, Meta, Claude, GPT-4o, ...)
  - Google Gemini
  - Groq        (free ultra-fast inference)
  - NVIDIA NIM  (free NVIDIA models)
  - Together AI
  - Anthropic
  - Generic OpenAI-compatible (any base_url + key)
"""

from __future__ import annotations

import os
import re
import json
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Any

from core.log_config import get_logger

_log = get_logger(__name__)


# ── Discovered model dataclass ────────────────────────────────────────────────

@dataclass
class DiscoveredModel:
    provider_type: str          # "openrouter" | "gemini" | "groq" | "nvidia" | ...
    model_id: str               # "deepseek/deepseek-r1"
    display_name: str           # "DeepSeek R1"
    context_window: int         # 163840
    max_output_tokens: int      # 4096
    supports_vision: bool       # True/False
    supports_tools: bool        # True/False
    cost_per_1m_input: float    # 0.0 = free
    cost_per_1m_output: float
    raw: dict = field(default_factory=dict, repr=False)

    @property
    def is_free(self) -> bool:
        return self.cost_per_1m_input == 0.0 and self.cost_per_1m_output == 0.0

    @property
    def tier(self) -> str:
        name_lower = self.display_name.lower() + self.model_id.lower()
        if any(k in name_lower for k in ("pro", "opus", "sonnet", "4o", "ultra", "think", "reason", "r1", "o1", "o3")):
            return "reasoning"
        if any(k in name_lower for k in ("flash", "haiku", "mini", "fast", "lite", "turbo", "instant")):
            return "fast"
        if "local" in name_lower or "oss" in name_lower:
            return "local"
        return "standard"

    @property
    def providers_yaml_id(self) -> str:
        """Safe ID for providers.yaml: e.g. 'deepseek/deepseek-r1' → 'openrouter-deepseek-r1'"""
        slug = re.sub(r"[^a-z0-9]+", "-", self.model_id.lower()).strip("-")
        prefix = self.provider_type.split("-")[0]
        return f"{prefix}-{slug}"

    def to_providers_yaml_entry(self) -> str:
        """Render a providers.yaml block for this model."""
        if self.provider_type == "openrouter":
            model_str = f"openrouter/{self.model_id}"
            api_key_env = "OPENROUTER_API_KEY"
            api_base = ""
        elif self.provider_type == "gemini":
            model_str = f"gemini/{self.model_id}"
            api_key_env = "GEMINI_API_KEY"
            api_base = ""
        elif self.provider_type == "groq":
            model_str = f"openai/{self.model_id}"
            api_key_env = "GROQ_API_KEY"
            api_base = "    api_base_default: https://api.groq.com/openai/v1\n"
        elif self.provider_type == "nvidia":
            model_str = f"openai/{self.model_id}"
            api_key_env = "NVIDIA_API_KEY"
            api_base = "    api_base_default: https://integrate.api.nvidia.com/v1\n"
        elif self.provider_type == "together":
            model_str = f"openai/{self.model_id}"
            api_key_env = "TOGETHER_API_KEY"
            api_base = "    api_base_default: https://api.together.xyz/v1\n"
        else:
            model_str = f"openai/{self.model_id}"
            api_key_env = f"{self.provider_type.upper()}_API_KEY"
            api_base = ""

        vision_str = "true" if self.supports_vision else "false"
        tools_str = "true" if self.supports_tools else "false"
        free_str = f"  # FREE\n" if self.is_free else ""

        return (
            f"{free_str}"
            f"  - id: {self.providers_yaml_id}\n"
            f"    model: {model_str}\n"
            f"    api_key_env: {api_key_env}\n"
            f"{api_base}"
            f"    tier: {self.tier}\n"
            f"    supports_vision: {vision_str}\n"
            f"    supports_tools: {tools_str}\n"
            f"    context_window: {self.context_window}\n"
            f"    max_output_tokens: {self.max_output_tokens}\n"
            f"    cost_per_1m_input: {self.cost_per_1m_input}\n"
            f"    cost_per_1m_output: {self.cost_per_1m_output}\n"
        )


# ── HTTP helper (no extra deps — uses stdlib urllib) ──────────────────────────

def _get(url: str, headers: dict[str, str], timeout: int = 15) -> Any:
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} from {url}: {body[:200]}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Connection failed to {url}: {e.reason}") from e


# ── Per-provider discovery functions ─────────────────────────────────────────

def _discover_openrouter(api_key: str) -> list[DiscoveredModel]:
    """OpenRouter: 300+ models across all providers, with pricing."""
    data = _get(
        "https://openrouter.ai/api/v1/models",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    models = []
    for m in data.get("data", []):
        pricing = m.get("pricing", {})
        try:
            cost_in = float(pricing.get("prompt", "0") or "0") * 1_000_000
            cost_out = float(pricing.get("completion", "0") or "0") * 1_000_000
        except (ValueError, TypeError):
            cost_in = cost_out = 0.0

        arch = m.get("architecture", {})
        modalities = arch.get("modality", "")
        supports_vision = "image" in str(modalities).lower()
        supports_tools = bool(m.get("top_provider", {}).get("is_moderated", False)) or True

        models.append(DiscoveredModel(
            provider_type="openrouter",
            model_id=m.get("id", ""),
            display_name=m.get("name", m.get("id", "")),
            context_window=m.get("context_length", 128_000),
            max_output_tokens=m.get("top_provider", {}).get("max_completion_tokens", 4096) or 4096,
            supports_vision=supports_vision,
            supports_tools=supports_tools,
            cost_per_1m_input=round(cost_in, 4),
            cost_per_1m_output=round(cost_out, 4),
            raw=m,
        ))
    return models


def _discover_gemini(api_key: str) -> list[DiscoveredModel]:
    """Google Gemini: list all models available with this key."""
    data = _get(
        f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
        headers={"Content-Type": "application/json"},
    )
    models = []
    for m in data.get("models", []):
        name = m.get("name", "")  # "models/gemini-2.0-flash"
        model_id = name.split("/")[-1] if "/" in name else name
        display = m.get("displayName", model_id)
        ctx = m.get("inputTokenLimit", 128_000) or 128_000
        out = m.get("outputTokenLimit", 8192) or 8192
        # Gemini is free up to quota
        models.append(DiscoveredModel(
            provider_type="gemini",
            model_id=model_id,
            display_name=display,
            context_window=ctx,
            max_output_tokens=out,
            supports_vision="vision" in display.lower() or "flash" in model_id or "pro" in model_id,
            supports_tools=True,
            cost_per_1m_input=0.0,   # free tier
            cost_per_1m_output=0.0,
            raw=m,
        ))
    return models


def _discover_groq(api_key: str) -> list[DiscoveredModel]:
    """Groq: ultra-fast free inference for open-source models."""
    data = _get(
        "https://api.groq.com/openai/v1/models",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    models = []
    for m in data.get("data", []):
        model_id = m.get("id", "")
        ctx = m.get("context_window", 128_000) or 128_000
        models.append(DiscoveredModel(
            provider_type="groq",
            model_id=model_id,
            display_name=model_id.replace("-", " ").replace("_", " ").title(),
            context_window=ctx,
            max_output_tokens=min(ctx, 8192),
            supports_vision="llava" in model_id.lower() or "vision" in model_id.lower(),
            supports_tools=True,
            cost_per_1m_input=0.0,   # Groq free tier
            cost_per_1m_output=0.0,
            raw=m,
        ))
    return models


def _discover_nvidia(api_key: str) -> list[DiscoveredModel]:
    """NVIDIA NIM: free NVIDIA-hosted models."""
    data = _get(
        "https://integrate.api.nvidia.com/v1/models",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    models = []
    for m in data.get("data", []):
        model_id = m.get("id", "")
        models.append(DiscoveredModel(
            provider_type="nvidia",
            model_id=model_id,
            display_name=model_id.split("/")[-1].replace("-", " ").title(),
            context_window=m.get("context_window", 128_000) or 128_000,
            max_output_tokens=4096,
            supports_vision="vision" in model_id.lower() or "vlm" in model_id.lower(),
            supports_tools=True,
            cost_per_1m_input=0.0,   # NVIDIA NIM free tier
            cost_per_1m_output=0.0,
            raw=m,
        ))
    return models


def _discover_together(api_key: str) -> list[DiscoveredModel]:
    """Together AI: 100+ open-source models."""
    data = _get(
        "https://api.together.xyz/v1/models",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    models = []
    for m in data if isinstance(data, list) else data.get("data", []):
        model_id = m.get("id", "")
        pricing = m.get("pricing", {})
        try:
            cost_in = float(pricing.get("input", "0") or "0")
            cost_out = float(pricing.get("output", "0") or "0")
        except (ValueError, TypeError):
            cost_in = cost_out = 0.0

        models.append(DiscoveredModel(
            provider_type="together",
            model_id=model_id,
            display_name=m.get("display_name", model_id),
            context_window=m.get("context_length", 32_768) or 32_768,
            max_output_tokens=4096,
            supports_vision="vision" in model_id.lower(),
            supports_tools=True,
            cost_per_1m_input=round(cost_in, 4),
            cost_per_1m_output=round(cost_out, 4),
            raw=m,
        ))
    return models


def _discover_generic_openai_compat(api_key: str, base_url: str, provider_name: str) -> list[DiscoveredModel]:
    """Generic OpenAI-compatible endpoint (vLLM, LM Studio, Ollama, etc.)."""
    base_url = base_url.rstrip("/")
    data = _get(
        f"{base_url}/models",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    models = []
    for m in data.get("data", []):
        model_id = m.get("id", "")
        models.append(DiscoveredModel(
            provider_type=provider_name,
            model_id=model_id,
            display_name=model_id,
            context_window=m.get("context_length", 4096) or 4096,
            max_output_tokens=4096,
            supports_vision=False,
            supports_tools=True,
            cost_per_1m_input=0.0,
            cost_per_1m_output=0.0,
            raw=m,
        ))
    return models


# ── Provider type auto-detection ──────────────────────────────────────────────

def detect_provider_from_key(api_key: str, base_url: str | None = None) -> str:
    """
    Heuristically detect provider from API key format or base_url.
    Returns: "openrouter" | "gemini" | "groq" | "nvidia" | "together" | "generic"
    """
    if base_url:
        url_lower = base_url.lower()
        if "openrouter" in url_lower:
            return "openrouter"
        if "groq" in url_lower:
            return "groq"
        if "nvidia" in url_lower or "nim" in url_lower:
            return "nvidia"
        if "together" in url_lower:
            return "together"
        if "googleapis" in url_lower or "generativelanguage" in url_lower:
            return "gemini"
        return "generic"

    key_lower = api_key.lower()
    if key_lower.startswith("sk-or-"):
        return "openrouter"
    if key_lower.startswith("gsk_"):
        return "groq"
    if key_lower.startswith("nvapi-"):
        return "nvidia"
    if key_lower.startswith("sk-tog-") or key_lower.startswith("together-"):
        return "together"
    if len(api_key) > 30 and "-" not in api_key[:10] and api_key.startswith("AI"):
        return "gemini"

    return "openrouter"   # default: try openrouter


# ── Main discovery entry point ────────────────────────────────────────────────

def discover_models(
    api_key: str,
    provider: str | None = None,
    base_url: str | None = None,
) -> list[DiscoveredModel]:
    """
    Given an API key (and optional provider hint or base_url),
    return the full list of available models with metadata.

    Args:
        api_key:  The API key to use
        provider: Optional explicit override: "openrouter"|"gemini"|"groq"|"nvidia"|"together"|"generic"
        base_url: Optional base URL for generic/custom endpoints

    Returns:
        List of DiscoveredModel objects, sorted free-first then by name
    """
    if not provider:
        provider = detect_provider_from_key(api_key, base_url)

    _log.info("Discovering models", extra={"provider": provider, "component": "discovery"})
    t0 = time.time()

    try:
        if provider == "openrouter":
            models = _discover_openrouter(api_key)
        elif provider == "gemini":
            models = _discover_gemini(api_key)
        elif provider == "groq":
            models = _discover_groq(api_key)
        elif provider == "nvidia":
            models = _discover_nvidia(api_key)
        elif provider == "together":
            models = _discover_together(api_key)
        else:
            if not base_url:
                raise ValueError("base_url is required for generic provider discovery")
            models = _discover_generic_openai_compat(api_key, base_url, provider)
    except Exception as e:
        _log.error("Model discovery failed", extra={"provider": provider, "exc": str(e), "component": "discovery"})
        raise

    elapsed = round(time.time() - t0, 2)
    _log.info(
        "Discovery complete",
        extra={"provider": provider, "count": len(models), "elapsed_s": elapsed, "component": "discovery"},
    )

    # Sort: free first, then by display name
    models.sort(key=lambda m: (0 if m.is_free else 1, m.display_name.lower()))
    return models
