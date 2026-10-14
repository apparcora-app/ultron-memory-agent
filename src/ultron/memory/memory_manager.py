"""
memory_manager.py — Thin, direct wrapper around Mem0's Memory class.

Design goals (as discussed in the tutorial):
  - Avoid wrapper-upon-wrapper: expose the raw Mem0 `Memory` object as
    `self.mem` so callers can access any method Mem0 provides directly.
  - Keep the public API small: `search`, `add`, `get_all`, `delete`.
  - All methods are synchronous (matching Mem0 OSS v0.x).
"""

from __future__ import annotations

import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    sys.path.append(str(Path(__file__).resolve().parent.parent))
    from pii_redaction import safe_redact_obj
except ImportError:
    def safe_redact_obj(x):
        return x

from mem0 import Memory

from ultron.core.config import AgentConfig, LLMConfig, VectorStoreConfig, build_mem0_config


class MemoryManager:
    """
    Manages long-term memory for a single user via Mem0.

    Parameters
    ----------
    user_id:
        Unique identifier for the user. All Mem0 operations are scoped to
        this ID so multiple users can share the same collection without cross-contamination.
    vector_store_cfg / llm_cfg / agent_cfg:
        Typed config objects built from environment variables.
    """

    def __init__(
        self,
        user_id: str,
        vector_store_cfg: VectorStoreConfig | None = None,
        llm_cfg: LLMConfig | None = None,
        agent_cfg: AgentConfig | None = None,
        qdrant_cfg: VectorStoreConfig | None = None,  # backwards compatibility
    ) -> None:
        self.user_id = user_id
        vector_cfg = vector_store_cfg or qdrant_cfg or VectorStoreConfig()
        llm_cfg = llm_cfg or LLMConfig()
        agent_cfg = agent_cfg or AgentConfig()
        self.top_k = agent_cfg.memory_top_k

        mem0_config = build_mem0_config(vector_cfg, llm_cfg)
        # Expose raw Memory object so advanced callers can use any Mem0 method.
        try:
            self.mem: Memory | None = Memory.from_config(config_dict=mem0_config)
        except Exception as e:
            print(f"  [MEMORY INIT ERROR] Vector store init error: {e}", file=sys.stderr)
            self.mem = None
            raise


    # ── public API ────────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        recency_bias: float = 0.3,
        top_k: int | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieve the top-K memories most semantically relevant to *query*.

        Returns a list of dicts with at least {"id": ..., "memory": ...}.
        """
        if not self.mem:
            raise RuntimeError("Mem0 Memory instance is not initialized")
        effective_k = limit or top_k or self.top_k
        try:
            results = self.mem.search(
                query=query,
                user_id=self.user_id,
                limit=effective_k * 2,
            )
            # Mem0 ≥0.1.x wraps results in {"results": [...]}
            if isinstance(results, dict):
                results = results.get("results", [])
            else:
                results = results or []

            for res in results:
                original_score = res.get("score", 0.0)
                decay = 0.0
                if "created_at" in res and res["created_at"]:
                    try:
                        # Assuming created_at is an ISO format string
                        created_time = datetime.fromisoformat(res["created_at"].replace("Z", "+00:00"))
                        age_days = (datetime.now(created_time.tzinfo) - created_time).total_seconds() / (24 * 3600)
                        decay = math.exp(-0.05 * max(0, age_days))
                    except Exception:
                        pass
                res["score"] = (1 - recency_bias) * original_score + recency_bias * decay

            results.sort(key=lambda x: x.get("score", 0.0), reverse=True)
            return results[:effective_k]
        except Exception as e:
            print(f"[MEMORY SEARCH ERROR] Error searching memories for user '{self.user_id}': {e}", file=sys.stderr)
            raise

    def add(
        self,
        messages: Any,
        infer: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Ingest a conversation turn and update the memory store.

        Mem0 internally:
          1. Summarises the messages.
          2. Extracts facts via the custom fact-extraction prompt.
          3. Compares to existing memories and applies ADD / UPDATE / DELETE
             operations via the custom memory-update prompt.

        Returns the raw Mem0 response dict (useful for debugging).
        """
        if not self.mem:
            raise RuntimeError("Mem0 Memory instance is not initialized")

        redacted_messages = safe_redact_obj(messages)
        try:
            kwargs: dict[str, Any] = {
                "messages": redacted_messages,
                "user_id": self.user_id,
                "infer": infer,
            }
            if metadata is not None:
                kwargs["metadata"] = metadata
            res = self.mem.add(**kwargs)
            if infer and messages and (not res or not res.get("results")):
                raise RuntimeError("Mem0 fact extraction yielded 0 results from non-empty input. LLM auth/quota failure likely.")
            return res
        except Exception as e:
            print(f"[MEMORY ADD ERROR] Error adding memory for user '{self.user_id}': {e}", file=sys.stderr)
            raise

    def get_all(self, top_k: int = 100) -> list[dict[str, Any]]:
        """Return every stored memory for this user (for inspection / debugging)."""
        if not self.mem:
            raise RuntimeError("Mem0 Memory instance is not initialized")
        try:
            results = self.mem.get_all(filters={"user_id": self.user_id}, top_k=top_k)
            if isinstance(results, dict):
                return results.get("results", [])
            return results or []
        except Exception as e:
            print(f"[MEMORY GET_ALL ERROR] Error fetching memories for user '{self.user_id}': {e}", file=sys.stderr)
            raise

    def delete(self, memory_id: str) -> None:
        """Manually delete a specific memory by its ID."""
        if not self.mem:
            raise RuntimeError("Mem0 Memory instance is not initialized")
        try:
            self.mem.delete(memory_id=memory_id)
        except Exception as e:
            print(f"[MEMORY DELETE ERROR] Error deleting memory '{memory_id}' for user '{self.user_id}': {e}", file=sys.stderr)
            raise

    def delete_all(self) -> None:
        """Delete all memories for this user."""
        if not self.mem:
            raise RuntimeError("Mem0 Memory instance is not initialized")
        try:
            self.mem.delete_all(user_id=self.user_id)
        except Exception as e:
            print(f"[MEMORY DELETE_ALL ERROR] Error deleting all memories for user '{self.user_id}': {e}", file=sys.stderr)
            raise

    def get_profile(self) -> str:
        """Get the current profile text from ultron.memory."""
        memories = self.get_all()
        return self.format_for_prompt(memories)

    # ── Layer 6: Emotional Context Tracking ─────────────────────────────────

    def detect_and_store_emotional_context(self, user_text: str) -> str:
        """
        Lightweight heuristic detector for Layer 6 Emotional Context Storage.
        Extracts user mood/tone signals (URGENT, FRUSTRATED, SATISFIED, ANALYTICAL).
        """
        text_lower = user_text.lower()
        sentiment = "NEUTRAL"
        if any(w in text_lower for w in ["asap", "urgent", "immediately", "emergency", "help!"]):
            sentiment = "URGENT"
        elif any(w in text_lower for w in ["wrong", "failed", "broken", "issue", "error", "not working"]):
            sentiment = "FRUSTRATED"
        elif any(w in text_lower for w in ["great", "awesome", "perfect", "thanks", "excellent"]):
            sentiment = "SATISFIED"
        elif any(w in text_lower for w in ["analyze", "calculate", "audit", "model"]):
            sentiment = "ANALYTICAL"

        if sentiment != "NEUTRAL":
            self.add([
                {"role": "user", "content": f"[User Emotional Context Signal: {sentiment}]"},
                {"role": "assistant", "content": f"Acknowledged user sentiment state: {sentiment}"},
            ])
        return sentiment

    # ── display helpers ───────────────────────────────────────────────────────

    def format_for_prompt(self, memories: list[dict[str, Any]]) -> str:
        """
        Render a list of memory dicts as a bullet-point string suitable for
        injecting into the system prompt.
        """
        if not memories:
            return "No memories yet."
        lines = []
        for i, m in enumerate(memories, 1):
            text = m.get("memory", m.get("text", str(m)))
            score = m.get("score")
            score_str = f"  [relevance: {score:.2f}]" if score is not None else ""
            lines.append(f"  {i}. {text}{score_str}")
        return "\n".join(lines)

