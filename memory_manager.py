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
import time
from datetime import datetime
from typing import Any

from mem0 import Memory

from config import AgentConfig, VectorStoreConfig, LLMConfig, build_mem0_config


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

    def _preflight_sanitize_chroma(self, chroma_dir: str) -> None:
        """
        Pre-flight sanitizer for ChromaDB SQLite storage.
        Prevents Rust panic 'range start index out of range for slice' caused by
        phantom migration records exceeding the installed ChromaDB binary's migration slice.
        """
        import os, sqlite3
        sqlite_file = os.path.join(chroma_dir, "chroma.sqlite3")
        if not os.path.isfile(sqlite_file):
            return

        try:
            conn = sqlite3.connect(sqlite_file)
            cur = conn.cursor()
            # Ensure migrations table exists
            has_mig = cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='migrations'").fetchone()
            if has_mig:
                # Installed ChromaDB binary supports: sysdb <= 9, metadb <= 5, embeddings_queue <= 2
                deleted = cur.execute(
                    "DELETE FROM migrations WHERE (dir='sysdb' AND version > 9) OR (dir='metadb' AND version > 5) OR (dir='embeddings_queue' AND version > 2)"
                ).rowcount
                if deleted > 0:
                    conn.commit()
                    print(f"  [MEMORY SANITIZER] Pruned {deleted} out-of-bounds migration records from {sqlite_file} to prevent Rust panic.")
            conn.close()
        except Exception as e:
            print(f"  [MEMORY SANITIZER WARNING] Could not sanitize {sqlite_file}: {e}")

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

        # Pre-flight sanitize the persistent Chroma directory to guarantee zero Rust slice panics
        if getattr(vector_cfg, "provider", "chroma") == "chroma":
            self._preflight_sanitize_chroma(getattr(vector_cfg, "path", "./data/chroma"))

        mem0_config = build_mem0_config(vector_cfg, llm_cfg)
        # Expose raw Memory object so advanced callers can use any Mem0 method.
        try:
            self.mem: Memory | None = Memory.from_config(config_dict=mem0_config)
        except Exception as e:
            print(f"  [MEMORY INIT ERROR] Vector store init error: {e}")
            self.mem = None


    # ── public API ────────────────────────────────────────────────────────────

    def search(self, query: str, recency_bias: float = 0.3) -> list[dict[str, Any]]:
        """
        Retrieve the top-K memories most semantically relevant to *query*.

        Returns a list of dicts with at least {"id": ..., "memory": ...}.
        """
        if not self.mem:
            return []
        try:
            results = self.mem.search(query=query, user_id=self.user_id, limit=self.top_k * 2)
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
            return results[:self.top_k]
        except Exception:
            return []

    def add(self, messages: list[dict[str, str]]) -> dict[str, Any]:
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
            return {"results": []}
        try:
            return self.mem.add(messages=messages, user_id=self.user_id)
        except Exception:
            return {"results": []}

    def get_all(self) -> list[dict[str, Any]]:
        """Return every stored memory for this user (for inspection / debugging)."""
        if not self.mem:
            return []
        try:
            results = self.mem.get_all(user_id=self.user_id)
            if isinstance(results, dict):
                return results.get("results", [])
            return results or []
        except Exception:
            return []

    def delete(self, memory_id: str) -> None:
        """Manually delete a specific memory by its ID."""
        if not self.mem:
            return
        try:
            self.mem.delete(memory_id=memory_id)
        except Exception:
            pass

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

