"""
subsystems/memory.py — Memory & Knowledge Subsystem for Ultron Protocol.

Encapsulates all persistent, episodic, semantic, and working memory operations:
- MemoryManager (LocalArtifactEngine with vector store / embeddings)
- CoreMemory (working memory blocks: profile, active task, scratchpad)
- GraphRAGEngine (causal knowledge graph & sub-graph traversal)
- TrajectoryManager (episodic winning tool traces)
- SkillManager (modular skills & directives)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from ultron.core.config import AgentConfig, LLMConfig, VectorStoreConfig
from ultron.memory.artifact_memory import LocalArtifactEngine as MemoryManager
from ultron.memory.trajectory_manager import TrajectoryManager
from ultron.skills.skill_manager import SkillManager

try:
    from core_memory import CoreMemory
except ImportError:
    CoreMemory = None

try:
    from graph_rag_engine import GraphRAGEngine
except ImportError:
    GraphRAGEngine = None


@dataclass
class MemorySubsystem:
    """Cohesive facade managing all memory, knowledge graph, skill, and trajectory components."""
    memory_manager: MemoryManager
    core_memory: Any | None = None
    graph_rag: Any | None = None
    trajectories: TrajectoryManager | None = None
    skills: SkillManager | None = None

    def search_memory(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search long-term semantic memory."""
        return self.memory_manager.search(query, limit=limit)

    def add_memory(self, content: str, metadata: dict[str, Any] | None = None) -> Any:
        """Add a memory entry."""
        return self.memory_manager.add(content, metadata=metadata)

    def get_profile(self) -> str:
        """Get the current profile text from ultron.memory."""
        return self.memory_manager.get_profile()

    @classmethod
    def create_default(
        cls,
        user_id: str = "default_user",
        vector_cfg: VectorStoreConfig | None = None,
        llm_cfg: LLMConfig | None = None,
        agent_cfg: AgentConfig | None = None,
        claude: Any = None,
        gemini: Any = None,
        provider: str = "gemini",
        telemetry: Any = None,
    ) -> MemorySubsystem:
        """Factory creating the production-grade memory subsystem."""
        llm_cfg = llm_cfg or LLMConfig()
        agent_cfg = agent_cfg or AgentConfig()
        vector_cfg = vector_cfg or VectorStoreConfig()

        memory_mgr = MemoryManager(
            user_id=user_id,
            vector_store_cfg=vector_cfg,
            llm_cfg=llm_cfg,
            agent_cfg=agent_cfg,
        )

        core_mem = None
        if CoreMemory is not None:
            try:
                core_mem = CoreMemory(user_id=user_id or "default_user")
            except Exception:
                core_mem = None

        trajectories = TrajectoryManager()
        skills = SkillManager()

        graph_rag = None
        if GraphRAGEngine is not None:
            try:
                db_path = os.path.join(getattr(llm_cfg, "data_dir", "./data"), "knowledge_graph.sqlite3")
                graph_rag = GraphRAGEngine(
                    db_path=db_path,
                    claude=claude,
                    gemini=gemini,
                    haiku_model=llm_cfg.chat_model_haiku,
                    gemini_model=llm_cfg.gemini_model,
                    provider=provider,
                    telemetry=telemetry,
                )
            except Exception:
                graph_rag = None

        return cls(
            memory_manager=memory_mgr,
            core_memory=core_mem,
            graph_rag=graph_rag,
            trajectories=trajectories,
            skills=skills,
        )
