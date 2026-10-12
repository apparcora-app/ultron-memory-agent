"""
subsystems/planning.py — Planning & Reasoning Subsystem for Ultron Protocol.

Encapsulates all task routing, reasoning trees, and hierarchical goal management:
- ComplexityRouter (haiku vs sonnet vs thinking routing)
- GoalDAGManager (multi-step dependency graph & execution tracking)
- HierarchicalPlanner (recursive subtask decomposition & HTNode trees)
- TreeOfThoughtsEngine (MCTS-style thought rollout & branch pruning)
- PromptOptimizerAgent (autonomous pre-execution prompt optimization)
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ultron.core.config import LLMConfig
from ultron.core.model_router import ComplexityRouter
from ultron.reasoning.goal_dag_manager import GoalDAGManager
from ultron.reasoning.hierarchical_planner import HierarchicalPlanner
from ultron.reasoning.prompt_optimizer import PromptOptimizerAgent
from ultron.reasoning.tot_engine import TreeOfThoughtsEngine


@dataclass
class PlanningSubsystem:
    """Cohesive facade managing routing, goal DAGs, hierarchical planning, and ToT reasoning."""
    router: ComplexityRouter
    goals: GoalDAGManager
    hierarchical_planner: HierarchicalPlanner
    tot_engine: TreeOfThoughtsEngine
    prompt_optimizer: PromptOptimizerAgent

    @classmethod
    def create_default(
        cls,
        llm_cfg: LLMConfig | None = None,
        claude: Any = None,
        gemini: Any = None,
        openrouter: Any = None,
        provider: str = "gemini",
        tool_executor: Any = None,
        trajectories: Any = None,
        telemetry: Any = None,
        call_raw_llm_fn: Callable[[str, str], str] | None = None,
    ) -> PlanningSubsystem:
        """Factory creating the production-grade planning subsystem."""
        llm_cfg = llm_cfg or LLMConfig()

        router = ComplexityRouter(
            haiku_model=llm_cfg.gemini_model_flash,
            sonnet_model="openrouter/deepseek/deepseek-chat" if openrouter else llm_cfg.gemini_model_thinking,
            threshold=5,
            llm_cfg=llm_cfg,
        )

        goals = GoalDAGManager()

        db_path = os.path.join(getattr(llm_cfg, "data_dir", "./data"), "hierarchical_plans.sqlite3")
        hierarchical_planner = HierarchicalPlanner(
            db_path=db_path,
            claude=claude,
            gemini=gemini,
            sonnet_model=llm_cfg.chat_model,
            haiku_model=llm_cfg.chat_model_haiku,
            gemini_model=llm_cfg.gemini_model,
            provider=provider,
            tool_executor=tool_executor,
            trajectory_manager=trajectories,
            telemetry=telemetry,
        )

        tot_engine = TreeOfThoughtsEngine(
            claude=claude,
            gemini=gemini,
            haiku_model=llm_cfg.chat_model_haiku,
            sonnet_model=llm_cfg.chat_model,
            gemini_model=llm_cfg.gemini_model,
            provider=provider,
            tool_executor=tool_executor,
            trajectory_manager=trajectories,
            telemetry=telemetry,
        )

        prompt_optimizer = PromptOptimizerAgent(
            call_llm_fn=call_raw_llm_fn or (lambda p, s="": ""),
            telemetry=telemetry,
        )

        return cls(
            router=router,
            goals=goals,
            hierarchical_planner=hierarchical_planner,
            tot_engine=tot_engine,
            prompt_optimizer=prompt_optimizer,
        )
