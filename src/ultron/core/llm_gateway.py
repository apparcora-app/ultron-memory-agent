"""
core/llm_gateway.py — Universal LLM Provider Gateway

Single entry point for ALL LLM API calls across ALL providers.
Implements the OpenHands/Hermes pattern:
  - Providers declared in providers.yaml (data-driven, zero code changes to add one)
  - Single completion() / acompletion() call regardless of provider
  - Capability-aware routing (vision, tools, cost, tier)
  - Per-provider circuit-breaker integration
  - Structured logging with correlation ID on every call

Adding a new provider:
  1. Add an entry to providers.yaml
  2. Set the required env var
  3. Done.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

load_dotenv()

from ultron.core.log_config import correlation_id_ctx, get_logger

_log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Provider spec (loaded from providers.yaml)
# ---------------------------------------------------------------------------

class ProviderSpec:
    """Immutable view of one provider entry from providers.yaml."""

    def __init__(self, raw: dict) -> None:
        self.id: str = raw["id"]
        self.model: str = raw["model"]
        self.tier: str = raw.get("tier", "standard")
        self.priority: int = raw.get("priority", 50)
        self.supports_vision: bool = raw.get("supports_vision", False)
        self.supports_tools: bool = raw.get("supports_tools", True)
        self.context_window: int = raw.get("context_window", 128_000)
        self.max_output_tokens: int = raw.get("max_output_tokens", 4096)
        self.temperature: float = raw.get("temperature", 0.3)
        self.cost_per_1m_input: float = raw.get("cost_per_1m_input", 0.0)
        self.local: bool = raw.get("local", False)

        # Resolve API key
        key_env = raw.get("api_key_env", "")
        self.api_key: str | None = os.environ.get(key_env) or raw.get("api_key_default") or None

        # Resolve base URL (for local / custom endpoints)
        base_env = raw.get("api_base_env", "")
        self.api_base: str | None = (
            os.environ.get(base_env)
            or raw.get("api_base_default")
            or None
        )

    def is_gemini(self) -> bool:
        return self.model.startswith("gemini/")

    def is_openai_compat(self) -> bool:
        return self.model.startswith("openai/") or self.model.startswith("openrouter/")

    def is_available(self) -> bool:
        """Return True if credentials are present (or it's a local/free provider)."""
        if self.local or self.cost_per_1m_input == 0.0:
            return True  # Free/local — always try
        return bool(self.api_key)

    def openai_model_name(self) -> str:
        """Strip the openai/ or openrouter/ prefix for SDK calls."""
        if self.model.startswith("openai/"):
            return self.model[7:]
        if self.model.startswith("openrouter/"):
            return self.model[11:]
        return self.model

    def gemini_model_name(self) -> str:
        """Strip the gemini/ prefix."""
        if self.model.startswith("gemini/"):
            return self.model[7:]
        return self.model


# ---------------------------------------------------------------------------
# Gateway
# ---------------------------------------------------------------------------

class LLMGateway:
    """
    Universal LLM call gateway.

    Usage:
        gateway = LLMGateway()

        # Capability-aware provider selection:
        candidates = gateway.get_capable_providers(needs_vision=True, needs_tools=True)

        # Direct call (async, OpenAI-compatible response):
        response = await gateway.acompletion(
            provider_id="gemini-flash",
            messages=[{"role": "user", "content": "Hello"}],
            tools=None,
        )

        # Or let the gateway pick the best available provider:
        response, used_id = await gateway.acompletion_auto(
            messages=..., needs_vision=False, needs_tools=True
        )
    """

    def __init__(self, providers_path: str | Path | None = None) -> None:
        if providers_path is None:
            # Check project root (parents[3] from src/ultron/core/llm_gateway.py)
            root_candidate = Path(__file__).resolve().parents[3] / "providers.yaml"
            src_candidate = Path(__file__).resolve().parents[2] / "providers.yaml"
            pkg_candidate = Path(__file__).resolve().parent.parent / "providers.yaml"
            if root_candidate.exists():
                providers_path = root_candidate
            elif pkg_candidate.exists():
                providers_path = pkg_candidate
            elif src_candidate.exists():
                providers_path = src_candidate
            else:
                providers_path = root_candidate
        self._path = Path(providers_path)
        self._registry: dict[str, ProviderSpec] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            _log.warning(
                "providers.yaml not found — gateway running with empty registry",
                extra={"path": str(self._path), "component": "llm_gateway"},
            )
            return
        raw = yaml.safe_load(self._path.read_text(encoding="utf-8"))
        providers = raw.get("providers", [])
        self._registry = {p["id"]: ProviderSpec(p) for p in providers}
        _log.info(
            "Provider registry loaded",
            extra={
                "provider_count": len(self._registry),
                "providers": list(self._registry.keys()),
                "component": "llm_gateway",
            },
        )

    def reload(self) -> None:
        """Hot-reload providers.yaml without restart."""
        self._load()

    def get_spec(self, provider_id: str) -> ProviderSpec:
        if provider_id not in self._registry:
            raise KeyError(f"Unknown provider '{provider_id}'. Available: {list(self._registry)}")
        return self._registry[provider_id]

    def get_capable_providers(
        self,
        needs_vision: bool = False,
        needs_tools: bool = False,
        tier: str | None = None,
        max_cost_per_1m: float | None = None,
    ) -> list[str]:
        """
        Return provider IDs that satisfy the given capability requirements,
        ordered by priority (ascending = higher priority first).
        """
        result = []
        for pid, spec in self._registry.items():
            if not spec.is_available():
                continue
            if needs_vision and not spec.supports_vision:
                continue
            if needs_tools and not spec.supports_tools:
                continue
            if tier and spec.tier != tier:
                continue
            if max_cost_per_1m is not None and spec.cost_per_1m_input > max_cost_per_1m:
                continue
            result.append((spec.priority, pid))
        result.sort()
        return [pid for _, pid in result]

    def get_provider_for_model_string(self, model_string: str) -> str | None:
        """
        Find the best matching provider ID for a legacy model string like:
          'gemini-3.6-flash', 'openrouter/deepseek/deepseek-chat', 'freellmapi', ...
        Returns None if no match.
        """
        model_lower = model_string.lower()

        # Exact match on provider model field
        for pid, spec in self._registry.items():
            if spec.model == model_string:
                return pid

        # Heuristic matching for legacy strings
        if model_lower.startswith("gemini"):
            # Find gemini provider whose model ends with this model name
            for pid, spec in self._registry.items():
                if spec.is_gemini() and spec.gemini_model_name() == model_string:
                    return pid
            # Fallback: first gemini provider
            for pid, spec in self._registry.items():
                if spec.is_gemini():
                    return pid

        if "freellmapi" in model_lower:
            for pid, spec in self._registry.items():
                if spec.local and spec.is_openai_compat():
                    return pid

        if model_lower.startswith("openrouter/"):
            for pid, spec in self._registry.items():
                if spec.model == model_string or spec.model == f"openrouter/{model_string[11:]}":
                    return pid
            # Fallback: first openrouter provider
            for pid, spec in self._registry.items():
                if spec.model.startswith("openrouter/"):
                    return pid

        return None

    from ultron.core.observability.langfuse_tracer import observe

    @observe(as_type="generation")
    async def acompletion(
        self,
        provider_id: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Make a single async LLM call to the specified provider.
        Returns a normalized dict:
          {
            "content": str,
            "tool_calls": list[dict] | None,
            "input_tokens": int,
            "output_tokens": int,
            "raw": <original response object>,
          }
        """
        spec = self.get_spec(provider_id)
        cid = correlation_id_ctx.get("no-cid")
        _log.info(
            "LLM call",
            extra={
                "provider": provider_id,
                "model": spec.model,
                "cid": cid,
                "component": "llm_gateway",
            },
        )

        temp = temperature if temperature is not None else spec.temperature
        max_tok = max_tokens if max_tokens is not None else spec.max_output_tokens

        try:
            if spec.is_gemini():
                res = await self._call_gemini(spec, messages, tools, system_prompt, temp, max_tok)
            elif spec.is_openai_compat():
                res = await self._call_openai_compat(spec, messages, tools, system_prompt, temp, max_tok)
            else:
                raise ValueError(f"Unknown model format for provider '{provider_id}': {spec.model}")

            from langfuse.decorators import langfuse_context
            langfuse_context.update_current_observation(
                input=messages,
                model=spec.model,
                output=res.get("content", ""),
                usage={
                    "input": res.get("input_tokens", 0),
                    "output": res.get("output_tokens", 0)
                }
            )
            return res
        except Exception as e:
            _log.error(f"LLM call failed for {provider_id}: {e}", exc_info=True)
            raise e

    async def _call_gemini(
        self,
        spec: ProviderSpec,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        system_prompt: str | None,
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        """Call Google Gemini API and normalize response."""
        try:
            from google import genai
            from google.genai import types as genai_types
        except ImportError as e:
            raise RuntimeError("google-genai package not installed. Run: pip install google-genai") from e

        api_key = spec.api_key or os.environ.get("GEMINI_API_KEY", "")
        client = genai.Client(api_key=api_key)

        # Build tool declarations
        gemini_tools = []
        if tools:
            funcs = [
                genai_types.FunctionDeclaration(
                    name=t["name"],
                    description=t.get("description", ""),
                    parameters=t.get("input_schema", {}),
                )
                for t in tools
            ]
            gemini_tools = [genai_types.Tool(function_declarations=funcs)]

        config = genai_types.GenerateContentConfig(
            system_instruction=system_prompt or "",
            tools=gemini_tools or None,
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        # Convert messages to Gemini contents
        contents = []
        for msg in messages:
            role = "user" if msg["role"] in ("user", "system") else "model"
            contents.append(
                genai_types.Content(
                    role=role,
                    parts=[genai_types.Part.from_text(text=str(msg.get("content", "")))],
                )
            )

        resp = await asyncio.to_thread(
            client.models.generate_content,
            model=spec.gemini_model_name(),
            contents=contents,
            config=config,
        )

        in_tok = getattr(getattr(resp, "usage_metadata", None), "prompt_token_count", 0) or 0
        out_tok = getattr(getattr(resp, "usage_metadata", None), "candidates_token_count", 0) or 0

        # Normalize tool calls
        tool_calls_out = None
        if resp.function_calls:
            tool_calls_out = [
                {"name": fc.name, "arguments": dict(fc.args) if fc.args else {}}
                for fc in resp.function_calls
            ]

        content = ""
        try:
            content = (resp.text or "").strip()
        except Exception:
            pass

        return {
            "content": content,
            "tool_calls": tool_calls_out,
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "raw": resp,
            "provider_id": spec.id,
        }

    async def _call_openai_compat(
        self,
        spec: ProviderSpec,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        system_prompt: str | None,
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        """Call any OpenAI-compatible API and normalize response."""
        try:
            from openai import AsyncOpenAI
        except ImportError as e:
            raise RuntimeError("openai package not installed. Run: pip install openai") from e

        client = AsyncOpenAI(
            api_key=spec.api_key or "sk-no-key",
            base_url=spec.api_base or "https://openrouter.ai/api/v1",
        )

        # Build OpenAI-format tools
        or_tools = None
        if tools:
            or_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t.get("description", ""),
                        "parameters": t.get("input_schema", {}),
                    },
                }
                for t in tools
                if "input_schema" in t
            ]

        # Inject system prompt as first message if not already present
        full_messages = list(messages)
        if system_prompt and (not full_messages or full_messages[0].get("role") != "system"):
            full_messages = [{"role": "system", "content": system_prompt}] + full_messages

        resp = await client.chat.completions.create(
            model=spec.openai_model_name(),
            messages=full_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=or_tools or None,
        )

        in_tok = getattr(getattr(resp, "usage", None), "prompt_tokens", 0) or 0
        out_tok = getattr(getattr(resp, "usage", None), "completion_tokens", 0) or 0

        message = resp.choices[0].message

        # Normalize tool calls
        tool_calls_out = None
        if getattr(message, "tool_calls", None):
            import json
            tool_calls_out = []
            for tc in message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except Exception:
                    args = {}
                tool_calls_out.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": args,
                })

        content = (getattr(message, "content", None) or "").strip()

        return {
            "content": content,
            "tool_calls": tool_calls_out,
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "raw": resp,
            "provider_id": spec.id,
        }

    async def acompletion_auto(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        system_prompt: str | None = None,
        needs_vision: bool = False,
        needs_tools: bool = False,
        **kwargs: Any,
    ) -> tuple[dict[str, Any], str]:
        """
        Try providers in priority order until one succeeds.
        Returns (normalized_response, provider_id_used).
        """
        candidates = self.get_capable_providers(
            needs_vision=needs_vision,
            needs_tools=needs_tools or bool(tools),
        )
        if not candidates:
            raise RuntimeError("No capable providers available in registry.")

        last_err: Exception | None = None
        for provider_id in candidates:
            try:
                result = await self.acompletion(
                    provider_id=provider_id,
                    messages=messages,
                    tools=tools,
                    system_prompt=system_prompt,
                    **kwargs,
                )
                return result, provider_id
            except Exception as e:
                _log.warning(
                    "Provider failed in auto-routing, trying next",
                    extra={"provider": provider_id, "exc": str(e), "component": "llm_gateway"},
                )
                last_err = e

        raise RuntimeError(f"All providers exhausted. Last error: {last_err}")


# Module-level singleton — used by agent.py
default_gateway = LLMGateway()
