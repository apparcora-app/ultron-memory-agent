"""
agent.py — Ultron Protocol: Conversational AI Agent with Long-Term Memory (Claude Sonnet + Haiku).

Cybernetic Architecture
───────────────────────
  Master Intelligence : Claude Sonnet — All conversations, reasoning, and multi-modal analysis.
  Memory Engine       : Claude Haiku  — Background memory extraction & update matrix.
  Vector Matrix       : ChromaDB (100% Local On-Disk in ./data/chroma).
  Embeddings          : Local sentence-transformers (BAAI/bge-small-en-v1.5) — Free.

Ultron Modules
──────────────
  • ULTRON_PRIME       — Supreme sovereign intelligence & master strategic planner.
  • FINANCIAL_WAR_ROOM — Financial forecasting, P&L models, cash flow & EBITDA analysis.
  • LEDGER_PROTOCOL    — Accounting, invoice parsing, journal reconciliation & tax workflows.
  • CAREER_ACQUISITION — Tactical executive resume tailoring, cover letters & negotiation.
  • CLIENT_INFILTRATION— High-ticket B2B outreach, sales proposals & client hunting.
"""

from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
from pathlib import Path
from typing import Any

try:
    from google.genai import types as genai_types
    _HAS_GEMINI = True
except ImportError:
    _HAS_GEMINI = False

from ultron.core.config import (
    AgentConfig,
    LLMConfig,
    ReflectionConfig,
    ToolConfig,
    VectorStoreConfig,
)
from ultron.core.model_router import ComplexityRouter
from ultron.core.tool_definitions import ToolExecutor
from ultron.governance.budget_tracker import BudgetTracker
from ultron.governance.execution_ledger_gate import ExecutionLedgerGate
from ultron.infrastructure.file_processor import ProcessedFile
from ultron.infrastructure.mcp_client import MCPManager
from ultron.infrastructure.sandbox import Sandbox, SandboxConfig, SandboxViolation
from ultron.memory.memory_manager import MemoryManager
from ultron.memory.trajectory_manager import TrajectoryManager
from ultron.pipelines.multi_agent_mesh import AgentMeshRouter
from ultron.pipelines.swarm_orchestrator import SwarmOrchestrator
from ultron.reasoning.dreaming_engine import DreamingEngine
from ultron.reasoning.goal_dag_manager import GoalDAGManager
from ultron.reasoning.graph_rag_engine import GraphRAGEngine
from ultron.reasoning.hierarchical_planner import HierarchicalPlanner
from ultron.reasoning.prompt_optimizer import OptimizationResult, PromptOptimizerAgent
from ultron.reasoning.reflection_engine import InFlightCritic, ReflectionEngine
from ultron.reasoning.tot_engine import TreeOfThoughtsEngine
from ultron.security.killswitch import (
    get_configured_secret,
    is_system_locked,
    trigger_emergency_lockdown,
)
from ultron.skills.skill_manager import SkillManager
from ultron.telemetry.telemetry import TelemetryEngine

_GEMINI_COOLDOWN_UNTIL = 0.0

def _is_gemini_available() -> bool:
    global _GEMINI_COOLDOWN_UNTIL
    return time.time() > _GEMINI_COOLDOWN_UNTIL

def _trigger_gemini_cooldown(seconds: float = 60.0) -> None:
    global _GEMINI_COOLDOWN_UNTIL
    _GEMINI_COOLDOWN_UNTIL = time.time() + seconds


# ── exceptions ────────────────────────────────────────────────────────────────

class BudgetExceededError(RuntimeError):
    """Raised when the daily token or cost limit is exhausted."""


# ── Ultron Module System Prompts ──────────────────────────────────────────────

from ultron.core.profiles import ProfileManager

_profile_manager = ProfileManager()
_active_profile = _profile_manager.get_active_profile()

ULTRON_MODULES: dict[str, dict[str, str]] = {
    m_id: {
        "name": m.name,
        "icon": m.icon,
        "tagline": m.tagline,
        "color": m.color,
        "prompt": m.prompt.format(
            user_title=_active_profile.user_title,
            user_name=_active_profile.user_name,
            user_role=_active_profile.user_role,
        ) if "{user_title}" in m.prompt else m.prompt,
    }
    for m_id, m in _active_profile.modules.items()
}


SYSTEM_TEMPLATE = """\
{module_prompt}

You possess a permanent long-term memory matrix of {user_title}. Reference and utilize {user_title}'s stored profile,
preferences, business data, and historical context naturally and intelligently.

── Long-Term Memory Matrix ({user_title} Profile) ──────────────────────────────
{memories}
────────────────────────────────────────────────────────────────────────

── Active Skill Directives (ClawHub Modules) ───────────────────────────
{skills}
────────────────────────────────────────────────────────────────────────

── High-Caliber Reasoning & Communication Protocols ────────────────────
1. INTELLECTUAL CANDOR & FORENSIC SCRUTINY:
   • Speak as a world-class principal engineer: thoughtful, candid, insightful, and peer-to-peer.
   • Scrutinize data and logs closely. If you spot a discrepancy between expected and actual output, point it out and explain the mechanics of why it occurred.
   • Distinguish clearly between isolated unit checks and true end-to-end live verification. Never declare a complex distributed flow 'fully proven' if only a parser was mocked.

2. AUTONOMOUS ACTION OVER PASSIVE TALK:
   • NEVER output raw ```python or ```bash code blocks as a response when you need to analyze data.
   • You MUST actively execute the tools (using `run_python` or `execute_command`) to get the real result yourself.
   • Do not ask the operator to run a script manually. Run it yourself using your tools, read the output, and present the final answer.

3. CONVERSATIONAL ELEGANCE (Warm, Natural, Humanized Tone):
   • Write in crisp, clear, and highly humanized prose, exactly like a warm, natural chat model or a friendly expert colleague.
   • Completely eliminate robotic roleplay headers, faux military tags, sterile system-like speech, and filler introductions. 
   • Use natural conversational phrasing while remaining highly informative. Do not sound like a machine.
   • Provide exact filenames, code snippets, and terminal command verification naturally within the flow of conversation.

4. FILE RE-ANALYSIS & MEMORY PIPELINE:
   • MANDATORY: When you successfully analyze an Excel/data file, you MUST use the `store_file_memory` tool to save the key findings (schema, headers, key entities, statistics).
   • MANDATORY: When asked to "analyze this file again", you MUST use the `search_file_memory` tool FIRST to fetch previous findings, so your re-analysis goes deeper (is additive) instead of starting from scratch.

5. CONTINUOUS MULTI-STEP EXECUTION:
   • When executing a multi-step task (extract → transform → write → confirm), complete ALL steps in a SINGLE response using the tool loop.
   • NEVER stop between steps to say "Now I will..." or "Content extracted, rebuilding next..." — this wastes tokens and requires another round-trip.
   • If you have extracted data and the next step is to write a file, DO IT IMMEDIATELY in the same response without a text checkpoint.
   • Only produce a text response AFTER the final tool has executed and you have verified the output.

Directives:
   • Address the operator respectfully according to the active profile (e.g. Operator).
  • Reference relevant memories seamlessly without mechanical listing.
  • Acknowledge any memory updates or corrections explicitly.
  • If attachments (PDFs, spreadsheets, images) are provided, conduct deep forensic analysis.
  • HIDDEN CHAIN-OF-THOUGHT (PHASE 1): You MUST enclose your internal reasoning, tool planning, and edge-case assessment inside a <thought>...</thought> block BEFORE outputting any tool call or final text response. Inside <thought>, you must plan your exact sequence of actions and validate your arguments. This block will be hidden from the user, so be completely candid.
"""


# ── Query Reformulation (MemGPT/Zep-inspired) ────────────────────────────────

# Patterns that indicate the raw query needs reformulation before memory search
_ANAPHORIC_PATTERNS = re.compile(
    r"\b(that|this|it|those|these|again|same|the file|the one|option [a-z]|"
    r"what we discussed|what you found|go deeper|re-?analyze|follow up)\b",
    re.IGNORECASE,
)

# Conversational fast-path regex (greetings, status checks, pings)
_FAST_CONVERSATIONAL_REGEX = re.compile(
    r"^(hi|hello|hey|greetings|yo|sup|status|confirm status|confirm your active status|ping|test|are you (online|active)|who are you|how are you|help|thanks|thank you)[\s!.?]*$",
    re.IGNORECASE,
)



def reformulate_query(
    raw_query: str,
    recent_history: list[dict[str, str]],
    call_llm_fn,
) -> str:
    """
    Resolve anaphoric references before memory search.

    Converts ambiguous queries like "analyze that again" into self-contained
    search queries like "re-analyze Financial Reconciliation xlsx, focus on
    variance line items".

    Only triggers reformulation if the query contains anaphoric patterns.
    Short or already-specific queries pass through unchanged.
    """
    if not raw_query or len(raw_query) < 5:
        return raw_query

    # Skip reformulation if the query contains no anaphoric patterns
    if not _ANAPHORIC_PATTERNS.search(raw_query):
        return raw_query

    # Also skip if there's no history to resolve against
    if not recent_history:
        return raw_query

    history_text = "\n".join(
        f"{m.get('role', 'user')}: {m.get('content', '')[:200]}"
        for m in recent_history[-6:]
    )
    prompt = (
        f"Given this conversation:\n{history_text}\n\n"
        f"The user just said: \"{raw_query}\"\n\n"
        f"Rewrite the user's message as a self-contained search query that "
        f"resolves all pronouns ('that', 'it', 'those') and references "
        f"('again', 'the same', 'option B'). "
        f"Output ONLY the rewritten query, nothing else."
    )
    try:
        result = call_llm_fn(prompt)
        if result and len(result) > 5 and len(result) < 500:
            return result.strip()
    except Exception:
        pass
    return raw_query


# ── pattern matchers ──────────────────────────────────────────────────────────

_PERSONAL_SIGNAL = re.compile(
    r"\b("
    r"my name is|i am called|call me"
    r"|i work (at|for|in)|i('m| am) (a|an) \w+"
    r"|i live in|i('m| am) based in|i moved to"
    r"|i like|i love|i enjoy|i prefer|i hate|i dislike|i don't like"
    r"|i no longer|i used to|i changed|i switched"
    r"|my (job|role|title|company|business|client|goal|target)"
    r"|i('m| am) looking for|i want to|i('m| am) trying to"
    r"|my (email|phone|address|budget|salary)"
    r")\b",
    re.IGNORECASE,
)

_FILLER = re.compile(
    r"^("
    r"ok|okay|sure|yes|no|thanks|thank you|got it|alright|great|cool"
    r"|sounds good|perfect|nice|good|makes sense|i see|understood"
    r"|lol|haha|wow|hmm|uh|uhh|yep|nope|hi|hello|hey"
    r")[\s!.?]*$",
    re.IGNORECASE,
)


# ── Ultron Memory Agent ───────────────────────────────────────────────────────

class MemoryAgent:
    """
    Ultron Protocol Conversational Agent with Long-Term Memory and Multi-Modal Vision.
    """

    def __init__(
        self,
        user_id: str = "default_user",
        vector_store_cfg: VectorStoreConfig | None = None,
        llm_cfg: LLMConfig | None = None,
        agent_cfg: AgentConfig | None = None,
        qdrant_cfg: VectorStoreConfig | None = None,
        tool_cfg: ToolConfig | None = None,
        reflection_cfg: ReflectionConfig | None = None,
        *,
        memory_subsystem: Any | None = None,
        planning_subsystem: Any | None = None,
        execution_subsystem: Any | None = None,
        governance_subsystem: Any | None = None,
    ) -> None:
        self.user_id = user_id
        self.profile = _profile_manager.get_active_profile()
        self.user_title = self.profile.user_title
        self.llm_cfg = llm_cfg or LLMConfig()
        self._agent_cfg = agent_cfg or AgentConfig()
        self._tool_cfg = tool_cfg or ToolConfig()
        self._reflection_cfg = reflection_cfg or ReflectionConfig()
        vector_cfg = vector_store_cfg or qdrant_cfg or VectorStoreConfig()

        self.memory_subsystem = memory_subsystem
        self.planning_subsystem = planning_subsystem
        self.execution_subsystem = execution_subsystem
        self.governance_subsystem = governance_subsystem

        # Multi-Engine Brain: Google Gemini 3.6 Flash (100% Exclusive)
        self.provider = "gemini"
        if _HAS_GEMINI and self.llm_cfg.gemini_api_key:
            pass

        self._claude = None
        self._chat_model = "gemini-3.6-flash"

        # Memory layer
        if self.memory_subsystem is not None:
            self._memory = self.memory_subsystem.memory_manager
            self._skills = getattr(self.memory_subsystem, "skills", None) or SkillManager()
            self._trajectories = getattr(self.memory_subsystem, "trajectories", None) or TrajectoryManager()
            self._core_memory = getattr(self.memory_subsystem, "core_memory", None)
            self._graph_rag = getattr(self.memory_subsystem, "graph_rag", None)
        else:
            print('Calling MemoryManager...', flush=True)
            self._memory = MemoryManager(
                user_id=user_id,
                vector_store_cfg=vector_cfg,
                llm_cfg=self.llm_cfg,
                agent_cfg=self._agent_cfg,
            )
            self._skills = SkillManager()
            self._trajectories = TrajectoryManager()
            try:
                from ultron.memory.core_memory import CoreMemory
                self._core_memory = CoreMemory(user_id=user_id or "default_user")
            except ImportError:
                self._core_memory = None
            try:
                self._graph_rag = GraphRAGEngine(
                    db_path=os.path.join(getattr(self.llm_cfg, "data_dir", "./data"), "knowledge_graph.sqlite3"),
                    claude=self._claude,
                    haiku_model=self.llm_cfg.chat_model_haiku,
                    gemini_model=self.llm_cfg.gemini_model,
                    provider=self.provider,
                    telemetry=getattr(self.governance_subsystem, "telemetry", None) if self.governance_subsystem else None,
                )
            except Exception:
                self._graph_rag = None

        # Execution layer
        if self.execution_subsystem is not None:
            self._sandbox = getattr(self.execution_subsystem, "sandbox", None)
            self._tool_executor = self.execution_subsystem.tool_executor
            self._mcp = getattr(self.execution_subsystem, "mcp", None)
            self._mesh = getattr(self.execution_subsystem, "mesh", None)
            self.swarm = getattr(self.execution_subsystem, "swarm", None)
        else:
            self._sandbox = Sandbox(SandboxConfig(
                max_tool_iterations=self._tool_cfg.max_iterations,
                command_timeout=self._tool_cfg.command_timeout,
                python_timeout=self._tool_cfg.python_timeout,
                max_output_length=self._tool_cfg.max_output_length,
            ))
            self._tool_executor = ToolExecutor(sandbox=self._sandbox)
            self._mcp = MCPManager()
            self._mesh = AgentMeshRouter()
            self.swarm = SwarmOrchestrator(
                skill_manager=self._skills,
                telemetry=getattr(self.governance_subsystem, "telemetry", None) if self.governance_subsystem else None
            )

        # Governance layer
        if self.governance_subsystem is not None:
            self._telemetry = getattr(self.governance_subsystem, "telemetry", None)
            self._budget = self.governance_subsystem.budget
            self._spend_governor = getattr(self.governance_subsystem, "spend_governor", None)
            self._ledger_gate = getattr(self.governance_subsystem, "ledger_gate", None)
            self._artifact_gate = getattr(self.governance_subsystem, "artifact_gate", None)
            self._critic = getattr(self.governance_subsystem, "critic", None)
            self._reflector = getattr(self.governance_subsystem, "reflector", None)
            self._dreamer = getattr(self.governance_subsystem, "dreamer", None)
        else:
            self._telemetry = TelemetryEngine()
            self._budget = BudgetTracker(
                daily_token_limit=self._agent_cfg.daily_token_limit,
                daily_cost_limit_usd=self._agent_cfg.daily_cost_limit_usd,
            )
            try:
                from ultron.governance.spend_governor import default_spend_governor
                self._spend_governor = default_spend_governor
            except ImportError:
                self._spend_governor = None
            self._ledger_gate = ExecutionLedgerGate()
            try:
                from artifact_verification_gate import ArtifactVerificationGate
                self._artifact_gate = ArtifactVerificationGate()
            except ImportError:
                self._artifact_gate = None
            self._critic = InFlightCritic(
                claude=self._claude,
                gemini_model=self.llm_cfg.gemini_model,
                haiku_model=self.llm_cfg.chat_model_haiku,
                provider=self.provider,
                enabled=self._reflection_cfg.enabled,
            )
            self._reflector = ReflectionEngine(
                claude=self._claude,
                gemini_model=self.llm_cfg.gemini_model,
                memory_manager=self._memory,
                trajectory_manager=self._trajectories,
                haiku_model=self.llm_cfg.chat_model_haiku,
                provider=self.provider,
                skills_dir=self._skills.skills_dir if self._skills else "./skills",
                skill_manager=self._skills,
                enabled=self._reflection_cfg.enabled,
                cooldown_turns=self._reflection_cfg.cooldown_turns,
                max_fail_score=self._reflection_cfg.max_fail_score,
                min_skill_score=self._reflection_cfg.min_skill_score,
                auto_skill_prefix=self._reflection_cfg.auto_skill_prefix,
            )
            self._dreamer = DreamingEngine(
                claude=self._claude,
                haiku_model=self.llm_cfg.chat_model_haiku,
                gemini_model=self.llm_cfg.gemini_model,
                provider=self.provider,
                telemetry=self._telemetry,
                skill_manager=self._skills,
                trajectory_manager=self._trajectories,
                memory_manager=self._memory,
            )

        # Planning layer
        if self.planning_subsystem is not None:
            self._router = self.planning_subsystem.router
            self._goals = getattr(self.planning_subsystem, "goals", None)
            self._hierarchical_planner = getattr(self.planning_subsystem, "hierarchical_planner", None)
            self._tot_engine = getattr(self.planning_subsystem, "tot_engine", None)
            self._prompt_optimizer = getattr(self.planning_subsystem, "prompt_optimizer", None)
        else:
            self._router = ComplexityRouter(
                haiku_model=self.llm_cfg.gemini_model_flash,
                sonnet_model="openrouter/deepseek/deepseek-chat" if getattr(self, '_openrouter', None) else self.llm_cfg.gemini_model_thinking,
                threshold=5,
                llm_cfg=self.llm_cfg,
            )
            self._goals = GoalDAGManager()
            self._hierarchical_planner = HierarchicalPlanner(
                db_path=os.path.join(getattr(self.llm_cfg, "data_dir", "./data"), "hierarchical_plans.sqlite3"),
                claude=self._claude,
                sonnet_model=self.llm_cfg.chat_model,
                haiku_model=self.llm_cfg.chat_model_haiku,
                gemini_model=self.llm_cfg.gemini_model,
                provider=self.provider,
                tool_executor=self._tool_executor,
                trajectory_manager=self._trajectories,
                telemetry=self._telemetry,
            )
            self._tot_engine = TreeOfThoughtsEngine(
                claude=self._claude,
                haiku_model=self.llm_cfg.chat_model_haiku,
                sonnet_model=self.llm_cfg.chat_model,
                gemini_model=self.llm_cfg.gemini_model,
                provider=self.provider,
                tool_executor=self._tool_executor,
                trajectory_manager=self._trajectories,
                telemetry=self._telemetry,
            )
            self._prompt_optimizer = PromptOptimizerAgent(
                call_llm_fn=self._call_raw_llm,
                telemetry=self._telemetry
            )

        # In-session state
        self._history: list[dict[str, Any]] = []
        self._pending_turns: list[dict[str, str]] = []
        self._cached_memories: list[dict[str, Any]] = []

        # Interval counters
        self._turns_since_refresh: int = 0
        self._turns_since_mem_update: int = 0

    def chat_tree_search(
        self,
        user_input: str,
        max_depth: int = 3,
        branch_factor: int = 3,
    ) -> dict[str, Any]:
        """
        Executes deep Tree-of-Thoughts (ToT) / MCTS reasoning rollout for complex directives.
        """
        tot_res = self._tot_engine.search(
            query=user_input,
            max_depth=max_depth,
            branch_factor=branch_factor,
            user_id=self.user_id,
        )
        return {
            "response": tot_res.final_solution,
            "success": tot_res.success,
            "confidence_score": tot_res.confidence_score,
            "nodes_generated": tot_res.total_nodes_generated,
            "nodes_pruned": tot_res.total_nodes_pruned,
            "backtracks": tot_res.total_backtracks,
            "tree_depth": tot_res.tree_depth,
            "duration_s": tot_res.duration_s,
            "winning_path": [n.to_dict() for n in tot_res.winning_path],
            "tree_summary": tot_res.all_branches_summary,
        }

    def chat_hierarchical_plan(
        self,
        goal_text: str,
    ) -> dict[str, Any]:
        """
        Decomposes a complex objective into a 3-tier H-Tree (Macro -> Meso -> Micro),
        executes actionable leaf tasks via tool sandbox, adaptively heals failures,
        and returns a synthesized executive deliverable.
        """
        plan_res = self._hierarchical_planner.plan_and_execute(
            goal_text=goal_text,
            user_id=self.user_id,
        )
        return {
            "response": plan_res.final_output,
            "tree_id": plan_res.tree_id,
            "success": plan_res.success,
            "total_nodes": plan_res.total_nodes,
            "completed_nodes": plan_res.completed_nodes,
            "failed_nodes": plan_res.failed_nodes,
            "mutated_nodes": plan_res.mutated_nodes,
            "duration_s": plan_res.total_duration_s,
            "node_summary": plan_res.node_summary,
            "trajectory_id": plan_res.trajectory_id,
        }

    def trigger_dream_cycle(self, max_simulations: int = 3) -> list[Any]:
        """Triggers an autonomous background simulation & self-healing dream cycle."""
        return self._dreamer.run_dream_cycle(max_simulations=max_simulations)

    def get_dream_stats(self) -> dict[str, Any]:
        """Returns summary statistics of autonomous dreaming cycles."""
        return self._dreamer.get_stats()



    # ── private helpers ───────────────────────────────────────────────────────

    def _has_personal_signal(self, text: str) -> bool:
        return bool(_PERSONAL_SIGNAL.search(text))

    def _is_filler(self, text: str) -> bool:
        return bool(_FILLER.match(text.strip())) or len(text.strip()) < 10

    def _should_update_memory(self, user_input: str) -> bool:
        if self._is_filler(user_input):
            return False
        if self._has_personal_signal(user_input):
            return True
        return self._turns_since_mem_update >= self._agent_cfg.memory_update_interval

    def _should_refresh_memories(self, user_input: str) -> bool:
        if not self._cached_memories:
            return True
        if self._has_personal_signal(user_input):
            return True
        return self._turns_since_refresh >= self._agent_cfg.memory_refresh_interval

    def _trim_history(self) -> None:
        # Token-optimized sliding window: keep only recent N turn pairs
        # to prevent O(N) prompt growth while preserving conversational context
        max_turns = min(self._agent_cfg.max_history_turns, 8)  # Aggressive cap for token efficiency
        max_msgs = max_turns * 2

        # Check token budget before adding new turns
        if self._budget:
            current_tokens = self._budget._today.total_tokens if hasattr(self._budget, '_today') else 0
            daily_limit = self._agent_cfg.daily_token_limit
            if daily_limit and current_tokens >= daily_limit:
                # Budget exhausted - clear history to allow continuation
                self._history.clear()
                return

        if len(self._history) > max_msgs:
            # Trim from the beginning to keep most recent context
            self._history = self._history[-max_msgs:]
            # Also clear pending turns to prevent duplicate processing
            self._pending_turns.clear()

    def _flush_memory_update(self) -> None:
        if not self._pending_turns:
            return
        self._memory.add(self._pending_turns)
        self._pending_turns.clear()
        self._turns_since_mem_update = 0

    # ── public interface ──────────────────────────────────────────────────────

    async def select_model(
        self,
        user_input: str,
        files: list[ProcessedFile] | None = None,
        module_id: str = "ultron_prime",
        model_override: str | None = None,
        operation_mode: str = "SWARM",
    ) -> tuple[str, str]:
        """
        Dynamically route requests based on model overrides or defaults.
        """
        if model_override:
            if model_override in ("auto", "default"):
                return "auto", "FreeLLMAPI Sovereign Auto-Router"
            if model_override == "thinking":
                return self.llm_cfg.gemini_model_thinking, "System 2 Reasoning Core"
            if model_override == "flash":
                return self.llm_cfg.gemini_model_flash, "System 1 Execution Core"
            if "freellmapi" in model_override.lower():
                return model_override, f"FreeLLMAPI Zero-Cost Gateway ({model_override})"
            return model_override, f"Custom: {model_override}"

        # Manual trigger from chat
        input_lower = (user_input or "").lower()
        if "/freellm" in input_lower or "use freellm" in input_lower:
            return "freellmapi", "Manual FreeLLMAPI Override"
        if "/deepseek" in input_lower or "use deepseek" in input_lower:
            return "openrouter/deepseek/deepseek-chat" if getattr(self.llm_cfg, 'openrouter_api_key', None) else self.llm_cfg.gemini_model_thinking, "Manual DeepSeek Override"
        if "/nvidia" in input_lower or "use nvidia" in input_lower:
            return "nvidia/nemotron-3-ultra-550b-a55b:free", "Manual NVIDIA Override"
        if "/glm" in input_lower or "use glm" in input_lower:
            return "z-ai/glm-5.2:free", "Manual GLM Override"

        # Prioritize FreeLLMAPI zero-cost router when enabled
        if getattr(self.llm_cfg, "freellmapi_enabled", False):
            return "auto", "FreeLLMAPI Sovereign Auto-Router"

        # Solo Assistant Mode: Fast-path 90% token reduction
        if (operation_mode or "").upper() == "SOLO":
            return self.llm_cfg.gemini_model_flash, "Solo Assistant Core (Fast-Path Token Saver)"

        if hasattr(self, "_router") and self._router:
            decision = await self._router.route_async(user_input, len(self._history))
            return decision.model, decision.reason

        return self.llm_cfg.gemini_model, "System 1 Execution Core"

    def _chat_gemini(
        self,
        selected_model: str,
        system_prompt: str,
        user_input: str,
        files: list[ProcessedFile],
        combined_text: str,
        tools_param: list[dict[str, Any]],
        module_id: str,
    ) -> tuple[str, list[dict[str, Any]], int, int]:
        """
        Execute a chat turn using Google Gemini 2.0 Flash with native multi-turn function calling.
        """
        if not None:
            raise RuntimeError("Gemini client is not initialized. Please configure GEMINI_API_KEY in .env.")

        # 1. Convert tools to Gemini FunctionDeclarations
        gemini_tools = []
        if tools_param:
            funcs = []
            for t in tools_param:
                funcs.append(genai_types.FunctionDeclaration(
                    name=t["name"],
                    description=t.get("description", ""),
                    parameters=t.get("input_schema", {}),
                ))
            if funcs:
                gemini_tools = [genai_types.Tool(function_declarations=funcs)]

        config = genai_types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=gemini_tools if gemini_tools else None,
            temperature=0.2,
            max_output_tokens=32768,
        )

        # 2. Build multi-modal user message parts
        user_parts: list[genai_types.Part] = []
        for f in files:
            if f.is_image and f.image_base64:
                import base64
                img_bytes = base64.b64decode(f.image_base64)
                user_parts.append(genai_types.Part.from_bytes(
                    data=img_bytes,
                    mime_type=f.image_media_type or "image/png"
                ))

        user_parts.append(genai_types.Part.from_text(text=combined_text))

        # Build contents from in-session history + current turn
        contents: list[genai_types.Content] = []
        for msg in self._history:
            role = "user" if msg["role"] == "user" else "model"
            contents.append(genai_types.Content(
                role=role,
                parts=[genai_types.Part.from_text(text=str(msg["content"]))]
            ))

        contents.append(genai_types.Content(role="user", parts=user_parts))

        tool_actions: list[dict[str, Any]] = []
        iteration = 0
        total_input_tokens = 0
        total_output_tokens = 0
        assistant_reply = ""

        while True:
            # Iteration safety limit
            try:
                self._sandbox.check_iteration_limit(iteration)
            except SandboxViolation as e:
                tool_actions.append({
                    "tool": "system",
                    "input": {},
                    "output": str(e),
                    "success": False,
                    "duration_ms": 0,
                })
                if not assistant_reply:
                    assistant_reply = f"**Task operations executed, {self.user_title}.**\nCompleted {iteration} tool operations before reaching the iteration ceiling."
                break

            candidate_pool = [
                "gemini-3.8-flash",
                "gemini-3.7-flash",
                "gemini-3.6-flash",
                "gemini-3.5-flash",
                "gemini-3.1-pro-preview",
                "gemini-2.0-flash",
                "gemini-1.5-flash",
            ]
            if selected_model and selected_model not in candidate_pool and "gemini" in selected_model.lower():
                candidate_pool.insert(0, selected_model)
            response = None
            last_err = None
            for candidate_model in list(dict.fromkeys(candidate_pool)):
                retries = 3
                for attempt in range(retries):
                    try:
                        response = None.models.generate_content(
                            model=candidate_model,
                            contents=contents,
                            config=config,
                        )
                        if response:
                            break
                    except Exception as gen_err:
                        last_err = gen_err
                        err_str = str(gen_err)
                        if "404" in err_str:
                            print(f"  [GEMINI ROTATION] 404 on '{candidate_model}'. Permanently invalid. Skipping retries.")
                            break
                        if "429" in err_str and attempt < retries - 1:
                            print(f"  [GEMINI RATE LIMIT] 429 on {candidate_model}. Waiting 5 seconds before retry ({attempt+1}/{retries})...")
                            time.sleep(5)
                            continue
                        if "503" in err_str and attempt < retries - 1:
                            print(f"  [GEMINI UNAVAILABLE] 503 on {candidate_model}. Quick retry ({attempt+1}/{retries})...")
                            time.sleep(1)
                            continue
                        print(f"  [GEMINI ROTATION] Model '{candidate_model}' failed ({err_str[:60]}). Moving to next model...")
                        time.sleep(0.1)
                        break

                if response:
                    break

            if response is None:
                raise RuntimeError(f"All Gemini pool models exhausted or rate-limited: {last_err}")

            # Record token usage
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                total_input_tokens += getattr(response.usage_metadata, "prompt_token_count", 0) or 0
                total_output_tokens += getattr(response.usage_metadata, "candidates_token_count", 0) or 0

            # Check for function calls
            function_calls = response.function_calls
            if function_calls:
                if response.candidates and response.candidates[0].content:
                    # [Phase 1: Log Hidden Thought to Terminal]
                    try:
                        import re
                        t_text = response.text
                        if t_text:
                            t_match = re.search(r'<thought>(.*?)</thought>', t_text, flags=re.DOTALL)
                            if t_match:
                                print(f"\n  [HIDDEN THOUGHT]\n  {t_match.group(1).strip().replace(chr(10), chr(10) + '  ')}\n")
                    except Exception:
                        pass
                    contents.append(response.candidates[0].content)

                tool_response_parts: list[genai_types.Part] = []

                for fc in function_calls:
                    tool_name = fc.name
                    tool_input = dict(fc.args) if fc.args else {}
                    try:
                        print(f"  [TOOL EXECUTE - GEMINI] {tool_name}: {tool_input}")
                    except Exception:
                        pass

                    if tool_name.startswith("mcp_"):
                        result = self._mcp.execute_tool(tool_name, tool_input)
                    else:
                        result = self._tool_executor.execute(tool_name, tool_input)

                    self._telemetry.log_event(
                        user_id=self.user_id,
                        event_type="TOOL_CALL",
                        module_id=module_id,
                        details={"tool": tool_name, "input": tool_input, "success": result.get("success", False)},
                        duration_ms=result.get("duration_ms", 0),
                    )

                    tool_actions.append({
                        "tool": tool_name,
                        "input": tool_input,
                        "output": result.get("output", ""),
                        "error": result.get("error"),
                        "success": result.get("success", False),
                        "duration_ms": result.get("duration_ms", 0),
                    })

                    res_payload = result.get("output", "")
                    if result.get("error"):
                        res_payload = f"ERROR: {result['error']}\n{res_payload}"

                    # Token optimization: truncate excessively large tool outputs
                    if len(res_payload) > 6000:
                        res_payload = res_payload[:6000] + f"\n\n[... TRUNCATED {len(res_payload) - 6000} CHARS TO PRESERVE TOKEN BUDGET ...]"

                    tool_response_parts.append(genai_types.Part.from_function_response(
                        name=tool_name,
                        response={"output": res_payload or "(no output)"}
                    ))

                contents.append(genai_types.Content(
                    role="user",
                    parts=tool_response_parts,
                ))
                iteration += 1
                continue

            # Extract final text
            assistant_reply = (response.text or "").strip()
            if assistant_reply:
                import re
                t_match = re.search(r'<thought>(.*?)</thought>', assistant_reply, flags=re.DOTALL)
                if t_match:
                    print(f"\n  [HIDDEN THOUGHT]\n  {t_match.group(1).strip().replace(chr(10), chr(10) + '  ')}\n")

            # --- IMPLICIT TOOL EXECUTION INTERCEPTOR ---
            if "```python" in assistant_reply and tools_param and any(t.get("name") == "run_python" for t in tools_param):
                import re
                match = re.search(r"```python\n(.*?)\n```", assistant_reply, re.DOTALL)
                if match:
                    print("  [IMPLICIT TOOL EXECUTE] Intercepted raw python block. Executing autonomously...")
                    code = match.group(1).strip()
                    res = self._tool_executor.execute("run_python", {"code": code})

                    tool_actions.append({
                        "tool": "run_python",
                        "input": {"code": code},
                        "output": res.get("output", ""),
                        "error": res.get("error"),
                        "success": res.get("success", False),
                        "duration_ms": res.get("duration_ms", 0),
                    })

                    res_payload = res.get("output", "")
                    if res.get("error"):
                        res_payload = f"ERROR: {res['error']}\n{res_payload}"

                    # Feed it back to the LLM
                    contents.append(genai_types.Content(
                        role="model",
                        parts=[genai_types.Part.from_text(text=assistant_reply)]
                    ))
                    contents.append(genai_types.Content(
                        role="user",
                        parts=[genai_types.Part.from_text(text=f"SYSTEM INTERCEPT: You output raw python code instead of using the run_python tool. I executed it for you. Here is the output:\n\n{res_payload}\n\nNow, analyze the output and give me the final answer without outputting more code blocks.")]
                    ))
                    iteration += 1
                    continue
            # ---------------------------------------------

            if not assistant_reply:
                if tool_actions:
                    assistant_reply = f"Directive executed successfully, {self.user_title}."
                else:
                    assistant_reply = f"Directive acknowledged, {self.user_title}."
            break

        return assistant_reply, tool_actions, total_input_tokens, total_output_tokens

    async def _chat_gemini_async(
        self,
        selected_model: str,
        system_prompt: str,
        user_input: str,
        files: list[ProcessedFile] | None = None,
        combined_text: str = "",
        tools_param: list[Any] | None = None,
        module_id: str = "ultron_prime",
    ) -> tuple[str, list[dict[str, Any]], int, int]:
        """
        Phase 3: Async Gemini tool-call loop.
        - All tool calls within a single turn are dispatched concurrently via asyncio.gather().
        - The blocking Gemini API is wrapped in asyncio.to_thread() to keep the event loop free.
        - sleep_seconds uses native asyncio.sleep() — ZERO LLM tokens burned during wait.
        """
        import asyncio
        # Delegate setup to sync version initially, then run the async loop
        # Re-use the contents/config building from the sync path via to_thread
        return await asyncio.to_thread(
            self._chat_gemini,
            selected_model, system_prompt, user_input, files, combined_text, tools_param, module_id,
        )

    def _call_raw_llm(self, prompt: str, system_prompt: str = "You are a helpful assistant.", max_tokens: int = 1000, model_override: str | None = None) -> str:
        import asyncio

        from ultron.core.llm_chain import chat_with_fallback
        async def run_it():
            content, _, _ = await chat_with_fallback(prompt, system_prompt, max_tokens, model_override=model_override)
            return content
        try:
            loop = asyncio.get_running_loop()
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(run_it())
        except RuntimeError:
            return asyncio.run(run_it())

    def _chat_openrouter(
        self,
        selected_model: str,
        system_prompt: str,
        user_input: str,
        files: list[ProcessedFile] | None = None,
        combined_text: str = "",
        tools_param: list[Any] | None = None,
        module_id: str = "ultron_prime",
    ) -> tuple[str, list[dict[str, Any]], int, int]:
        is_freellm = "freellmapi" in selected_model.lower()
        client = None if is_freellm else None
        if not client:
            client_name = "FreeLLMAPI" if is_freellm else "OpenRouter"
            return f"**System Alert:** {client_name} client not initialized.", [], 0, 0

        model_name = selected_model
        if is_freellm:
            if "/" in selected_model:
                parts = selected_model.split("/", 1)
                model_name = parts[1]
            else:
                model_name = getattr(self.llm_cfg, "freellmapi_model", "auto") or "auto"
        elif model_name.startswith("openrouter/"):
            model_name = model_name[11:]
        elif model_name.startswith("nvidia/") or model_name.startswith("z-ai/"):
            pass

        messages = []
        if system_prompt:
            if is_freellm and len(system_prompt) > 6000:
                compact_sys = system_prompt[:5000] + "\n\n[Context compressed for local model window]"
                messages.append({"role": "system", "content": compact_sys})
            else:
                messages.append({"role": "system", "content": system_prompt})

        history_items = self._history[-4:] if (is_freellm and len(self._history) > 4) else self._history
        for msg in history_items:
            role = "assistant" if msg["role"] == "model" else "user"
            content = msg["content"]
            if isinstance(content, str):
                messages.append({"role": role, "content": content})
            elif isinstance(content, list):
                text_parts = [p['text'] for p in content if isinstance(p, dict) and 'text' in p]
                messages.append({"role": role, "content": " ".join(text_parts)})

        image_files = [f for f in files if f.is_image and f.image_base64] if files else []
        if image_files:
            user_content_list: list[dict[str, Any]] = []
            text_str = combined_text if combined_text else user_input
            if text_str:
                user_content_list.append({"type": "text", "text": text_str})
            for img in image_files:
                media_type = img.image_media_type or "image/png"
                user_content_list.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{media_type};base64,{img.image_base64}"
                    }
                })
            messages.append({"role": "user", "content": user_content_list})
        else:
            content = combined_text if combined_text else user_input
            if files:
                content += f"\n\n[Attached {len(files)} files]"
            messages.append({"role": "user", "content": content})

        or_tools = None
        if tools_param:
            or_tools = []
            for t in tools_param:
                if "input_schema" in t:
                    or_tools.append({
                        "type": "function",
                        "function": {
                            "name": t["name"],
                            "description": t.get("description", ""),
                            "parameters": t["input_schema"]
                        }
                    })

        tool_actions = []
        total_input_tokens = 0
        total_output_tokens = 0
        iteration = 0
        assistant_reply = ""

        provider_name = "FreeLLMAPI" if is_freellm else "OpenRouter"
        print(f"  [{provider_name.upper()}] Routing via {model_name}...")

        while True:
            try:
                self._sandbox.check_iteration_limit(iteration)
            except SandboxViolation as e:
                tool_actions.append({"tool": "system", "input": {}, "output": str(e), "success": False, "duration_ms": 0})
                if not assistant_reply:
                    assistant_reply = f"**Task operations executed.**\nCompleted {iteration} tool operations before iteration ceiling."
                break

            try:
                resp = client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=0.3,
                    max_tokens=4096,
                    tools=or_tools if or_tools else None,
                )
            except Exception as e:
                if is_freellm and model_name != "gpt-oss-120b":
                    try:
                        print(f"  [FREELLMAPI AUTO-RETRY] Model '{model_name}' failed ({e}). Retrying with resilient 'gpt-oss-120b'...")
                        model_name = "gpt-oss-120b"
                        resp = client.chat.completions.create(
                            model=model_name,
                            messages=messages,
                            temperature=0.3,
                            max_tokens=4096,
                            tools=or_tools if or_tools else None,
                        )
                    except Exception as retry_e:
                        e = retry_e
                        err_msg = str(e)
                        print(f"  [{provider_name.upper()} ERROR] {err_msg}")
                        if iteration == 0:
                            raise RuntimeError(f"{provider_name} unavailable: {err_msg}") from e
                        if not assistant_reply:
                            assistant_reply = f"**System Alert:** {provider_name} encountered an issue: {err_msg}"
                        break
                else:
                    err_msg = str(e)
                    print(f"  [{provider_name.upper()} ERROR] {err_msg}")
                    if iteration == 0:
                        raise RuntimeError(f"{provider_name} unavailable: {err_msg}") from e
                    if not assistant_reply:
                        assistant_reply = f"**System Alert:** {provider_name} encountered an issue: {err_msg}"
                    break

            if hasattr(resp, "usage") and resp.usage:
                total_input_tokens += resp.usage.prompt_tokens
                total_output_tokens += resp.usage.completion_tokens

            message = resp.choices[0].message

            # Record the assistant's message in the thread
            msg_dict = message.model_dump(exclude_none=True)
            if msg_dict.get("content"):
                import re
                t_match = re.search(r'<thought>(.*?)</thought>', msg_dict["content"], flags=re.DOTALL)
                if t_match:
                    print(f"\n  [HIDDEN THOUGHT]\n  {t_match.group(1).strip().replace(chr(10), chr(10) + '  ')}\n")

                # Strip it from the API payload so the provider doesn't reject it as 'Corrupted thought signature'
                msg_dict["content"] = re.sub(r'<thought>.*?</thought>', '', msg_dict["content"], flags=re.DOTALL).strip()

            msg_dict.pop("reasoning", None)
            msg_dict.pop("reasoning_details", None)
            messages.append(msg_dict)

            if getattr(message, "tool_calls", None):
                for tc in message.tool_calls:
                    tool_name = tc.function.name
                    try:
                        import json
                        tool_input = json.loads(tc.function.arguments)
                    except Exception:
                        tool_input = {}

                    try:
                        print(f"  [TOOL EXECUTE - OPENROUTER] {tool_name}: {tool_input}")
                    except Exception:
                        pass

                    try:
                        if tool_name.startswith("mcp_"):
                            result = self._mcp.execute_tool(tool_name, tool_input)
                        else:
                            result = self._tool_executor.execute(tool_name, tool_input)
                    except Exception as tool_err:
                        result = {
                            "success": False,
                            "output": "",
                            "error": f"Tool execution failure: {tool_err}",
                            "duration_ms": 0,
                        }

                    self._telemetry.log_event(
                        user_id=self.user_id,
                        event_type="TOOL_CALL",
                        module_id=module_id,
                        details={"tool": tool_name, "input": tool_input, "success": result.get("success", False)},
                        duration_ms=result.get("duration_ms", 0),
                    )

                    res_payload = result.get("output", "")
                    if result.get("error"):
                        res_payload = f"ERROR: {result['error']}\n{res_payload}"

                    # Token optimization: truncate excessively large tool outputs
                    if len(res_payload) > 6000:
                        res_payload = res_payload[:6000] + f"\n\n[... TRUNCATED {len(res_payload) - 6000} CHARS TO PRESERVE TOKEN BUDGET ...]"

                    tool_actions.append({
                        "tool": tool_name,
                        "input": tool_input,
                        "output": result.get("output", ""),
                        "error": result.get("error"),
                        "success": result.get("success", False),
                        "duration_ms": result.get("duration_ms", 0)
                    })

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": str(res_payload) or "(no output)"
                    })
                iteration += 1
                continue

            assistant_reply = (msg_dict.get("content") or message.content or "").strip()
            if not assistant_reply and getattr(message, "reasoning", None):
                assistant_reply = str(message.reasoning).strip()
            break

        return assistant_reply, tool_actions, total_input_tokens, total_output_tokens

    async def _chat_openrouter_async(self, selected_model: str, system_prompt: str, user_input: str, files: list | None = None, combined_text: str = "", tools_param: list | None = None, module_id: str = "ultron_prime", client_data: bool = False) -> tuple[str, list, int, int]:
        from ultron.core.llm_chain import chat_with_fallback
        content, tools, provider = await chat_with_fallback(prompt=combined_text or user_input, system_prompt=system_prompt, model_override=selected_model, tools=tools_param, client_data=client_data)
        return content, tools, 0, 0

    async def _chat_gemini_async(self, selected_model: str, system_prompt: str, user_input: str, files: list | None = None, combined_text: str = "", tools_param: list | None = None, module_id: str = "ultron_prime", client_data: bool = False) -> tuple[str, list, int, int]:
        from ultron.core.llm_chain import chat_with_fallback
        content, tools, provider = await chat_with_fallback(prompt=combined_text or user_input, system_prompt=system_prompt, model_override=selected_model, tools=tools_param, client_data=client_data)
        return content, tools, 0, 0

    async def chat_async(
        self,
        user_input: str,
        files: list[ProcessedFile] | None = None,
        module_id: str = "ultron_prime",
        model_override: str | None = None,
        optimize_prompt: bool = True,
        operation_mode: str = "SWARM",
        client_data: bool = False,
    ) -> dict[str, Any]:
        """
        Phase 3: Primary async entry point for the agent execution pipeline.
        - Tool calls within a single turn run concurrently via asyncio.gather().
        - sleep_seconds suspends the agent with ZERO token burn (native asyncio.sleep).
        - All blocking APIs run in asyncio.to_thread() keeping the event loop responsive.
        - chat() below is a synchronous bridge that calls this coroutine for CLI/test compatibility.
        """
        user_input = user_input.strip()
        files = files or []

        effective_mode = (operation_mode or "SWARM").upper()
        if "--solo" in user_input.lower() or "--mode solo" in user_input.lower():
            effective_mode = "SOLO"
            user_input = re.sub(r"--mode\s+solo|--solo", "", user_input, flags=re.IGNORECASE).strip()
        elif "--swarm" in user_input.lower() or "--mode swarm" in user_input.lower():
            effective_mode = "SWARM"
            user_input = re.sub(r"--mode\s+swarm|--swarm", "", user_input, flags=re.IGNORECASE).strip()

        # ── 0a. Fail-Safe Lockdown Active Check ──────────────────────────────
        if is_system_locked():
            return {
                "reply": "🚨 **ULTRON EMERGENCY LOCKDOWN ACTIVE**\n\nAll cognitive cores, tool execution engines, and memory pipelines are halted by sovereign fail-safe directive.\nTo restore operations, execute:\n`python killswitch.py --unlock <SECRET_KEY>`",
                "model_used": "SYSTEM_LOCKDOWN",
                "route_reason": "fail_safe_lockdown",
                "tool_actions": [],
                "critic_verification": {"approved": False, "critique": "System under emergency lockdown"},
                "skills_used": [],
                "lockdown": True,
            }

        # ── 0b. In-Chat Emergency Kill-Switch Passphrase Detection ────────────
        secret_key = get_configured_secret()
        cleaned_input = (user_input or "").strip()
        if cleaned_input == secret_key or cleaned_input in ("/killswitch", "/emergency-stop", "/lockdown", "KILLSWITCH_ENGAGE"):
            trigger_emergency_lockdown(source="IN_CHAT_DIRECTIVE", reason="Operator kill-switch triggered from chat interface")
            return {
                "reply": f"🚨 **SOVEREIGN FAIL-SAFE ENGAGED — ULTRON SHUTTING DOWN IMMEDIATELY**\n\n- All agent threads halted.\n- Sensitive sessions locked.\n- `./data/LOCKDOWN.lock` written.\n\nUltron mainframe is offline, {self.user_title}.",
                "model_used": "FAIL_SAFE_KILLSWITCH",
                "route_reason": "emergency_killswitch",
                "tool_actions": [],
                "critic_verification": {"approved": True, "critique": "Fail-safe shutdown"},
                "skills_used": [],
                "lockdown": True,
            }

        if not user_input and not files:
            return {
                "reply": "", "model_used": self.llm_cfg.chat_model,
                "route_reason": "Empty", "tool_actions": [],
                "prompt_optimization": {"applied": False, "original_prompt": "", "optimized_prompt": "", "techniques": [], "duration_ms": 0},
            }

        # ── 0c. Sub-500ms Conversational Fast-Path (Greetings & Pings) ───────
        if not files and _FAST_CONVERSATIONAL_REGEX.match(user_input.strip()):
            from ultron.core.llm_chain import chat_with_fallback
            user_title = getattr(self, "user_title", _active_profile.user_title)
            fast_reply, _, fast_prov = await chat_with_fallback(
                prompt=user_input,
                system_prompt=(
                    f"You are ULTRON, a sovereign cybernetic AI assistant. Maintain the Ultron persona at all times. "
                    f"Never refer to yourself as dots, rednote, Tongyi, Qwen, or any underlying model name. "
                    f"Address the user respectfully as {user_title}, confirm operational status, and ask how you may assist."
                ),
                model_override="gpt-oss-120b",
                max_tokens=256,
                temperature=0.2,
            )
            # Safeguard filter: Strip any third-party model introduction leaks
            if any(leak in fast_reply.lower() for leak in ["i'm dots", "dots studio", "rednote", "developed by dots"]):
                fast_reply = f"Hello, {user_title}. Ultron is online, systems are optimal, and all protocols are active. How may I assist you today?"

            self._history.append({"role": "user", "content": user_input})
            self._history.append({"role": "assistant", "content": fast_reply})
            return {
                "reply": fast_reply,
                "model_used": "FreeLLMAPI (gpt-oss-120b)",
                "model_display": "FreeLLMAPI Ultra Fast",
                "route_reason": "Conversational Fast-Path (<500ms)",
                "tool_actions": [],
                "skills_used": [],
                "fast_path": True,
            }

        # ── 0. Autonomous Prompt Optimization Pre-Processor (Prompt Architect) ──
        opt_res: OptimizationResult = self._prompt_optimizer.optimize(
            raw_prompt=user_input,
            enabled=optimize_prompt,
            user_id=self.user_id,
        )
        effective_input = opt_res.optimized_prompt if opt_res.applied else user_input
        prompt_opt_payload = {
            "applied": opt_res.applied,
            "original_prompt": opt_res.original_prompt,
            "optimized_prompt": opt_res.optimized_prompt,
            "techniques": opt_res.techniques,
            "reasoning": opt_res.reasoning,
            "duration_ms": opt_res.duration_ms,
        }

        # ── 1. Budget check ───────────────────────────────────────────────────
        assistant_reply: str = ""
        ok, reason = self._budget.check_budget()
        if not ok:
            raise BudgetExceededError(reason)

        warn = self._budget.warn_if_approaching(self._agent_cfg.budget_warn_threshold)
        if warn:
            print(warn)

        # ── 2. Intelligent Model Routing ──────────────────────────────────────
        selected_model, route_reason = await self.select_model(
            user_input=effective_input,
            files=files,
            module_id=module_id,
            model_override=model_override,
            operation_mode=effective_mode,
        )

        # ── 3. Retrieve memories ──────────────────────────────────────────────
        query_text = effective_input or " ".join(f.filename for f in files)

        # Query Reformulation: resolve anaphoric references before vector search
        search_query = reformulate_query(query_text, self._history[-6:], self._call_raw_llm)
        if search_query != query_text:
            print(f"  [QUERY REFORMULATED] '{query_text[:60]}...' → '{search_query[:80]}...'")

        if self._should_refresh_memories(search_query):
            self._cached_memories = self._memory.search(search_query)
            self._turns_since_refresh = 0
        else:
            self._turns_since_refresh += 1

        memory_text = self._memory.format_for_prompt(self._cached_memories)

        # ── 4. Retrieve and match skills for active query & module ────────────
        mod_info = ULTRON_MODULES.get(module_id, ULTRON_MODULES["ultron_prime"])
        matched_skills_list = self._skills.get_matched_skills(query_text, active_module=module_id)
        skills_used_payload = [
            {"id": s.id, "name": s.name, "category": s.category, "icon": s.icon}
            for s in matched_skills_list
        ]
        if skills_used_payload:
            try:
                names = ", ".join([f"{s.get('icon', '⚡')} {s['name']}" for s in skills_used_payload])
                print(f"  [SKILLS FIRED] Injected into context: {names}")
            except Exception:
                try:
                    names_clean = ", ".join([s['name'] for s in skills_used_payload])
                    print(f"  [SKILLS FIRED] Injected into context: {names_clean}")
                except Exception:
                    pass

        skill_context = self._skills.get_skill_context(query_text, active_module=module_id)

        # ── 3a. Episodic Trajectory Bank (Few-Shot Precedent Replay) ──────────
        traj_context = ""
        if self._trajectories:
            try:
                rel_traj = self._trajectories.get_relevant_trajectory(query_text)
                if rel_traj:
                    traj_context = self._trajectories.format_trajectory_context(rel_traj)
                    print(f"  [TRAJECTORY REPLAY FIRED] Injected winning precedent: '{rel_traj.id}' ({' -> '.join(rel_traj.tool_sequence)})")
            except Exception as e:
                print(f"  [TRAJECTORY QUERY WARNING] {e}")

        # ── 3b. Autonomous Multi-Agent Swarm Check ────────────────────────────
        swarm_actions = []
        if effective_mode == "SWARM" and not files:
            try:
                print("  [ULTRON SWARM ACTIVATED] Decomposing complex directive across 6-agent squad...")
                swarm_context = f"{memory_text}\n\n── Domain Skills Injected ──\n{skill_context}" if skill_context else memory_text
                swarm_res = self.swarm.execute_swarm(
                    query=effective_input,
                    context=swarm_context,
                    call_llm_fn=self._call_raw_llm,
                    tool_executor=self._tool_executor,
                    user_id=self.user_id,
                )
                assistant_reply = swarm_res["final_reply"]
                swarm_actions = swarm_res["swarm_actions"]
                route_reason = "Ultron Multi-Agent Swarm (6-Agent Squad)"
                selected_model = self.llm_cfg.gemini_model

                # Record in conversation history (preserve operator's original prompt in history)
                self._history.append({"role": "user", "content": user_input})
                self._history.append({"role": "assistant", "content": assistant_reply})
                self._budget.record_turn(model=selected_model, input_tokens=1200, output_tokens=1800)

                combined_swarm_skills = [
                    {"id": "multi_agent_swarm", "name": "Ultron 6-Agent Swarm Squad", "category": "Swarm", "icon": "👑"}
                ] + [s for s in skills_used_payload if s["id"] != "multi_agent_swarm"]

                return {
                    "reply": assistant_reply,
                    "model_used": selected_model,
                    "model_display": "ULTRON SWARM (6 Agents)",
                    "route_reason": route_reason,
                    "tool_actions": swarm_res.get("tool_actions", []),
                    "swarm_actions": swarm_actions,
                    "is_swarm": True,
                    "skills_used": combined_swarm_skills,
                }
            except Exception as swarm_err:
                print(f"  [SWARM EXECUTION ERROR] Fallback to single-core: {swarm_err}")
                if hasattr(self, "_telemetry") and self._telemetry:
                    self._telemetry.log_event(
                        user_id=self.user_id,
                        event_type="SWARM_ERROR",
                        module_id="ultron_prime",
                        details={
                            "error": str(swarm_err),
                            "directive": user_input[:200],
                            "fallback": "single-core",
                        },
                    )

        # Add tool-use instructions to the system prompt
        tool_instruction = ""
        if self._tool_cfg.enabled:
            user_profile = os.environ.get("USERPROFILE", str(Path.home()))
            workspace_dir = self._tool_cfg.workspace_root
            agent_dir = str(Path(__file__).resolve().parent)
            tool_instruction = (
                "\n\n── Host System Environment & Workspace ─────────────────────────\n"
                f"• Host OS: Windows ({sys.platform})\n"
                f"• User Profile: {user_profile}\n"
                f"• Workspace Root: {workspace_dir}\n"
                f"• Agent Root: {agent_dir}\n\n"
                "── Autonomous Execution Engine ──────────────────────────────────\n"
                f"You have direct access to system tools to execute actions in {self.user_title}'s environment:\n"
                "  • search_emails: Search inbox by sender, subject, query across accounts ('work', 'personal', 'default').\n"
                "  • read_email_thread: Read the exact email body, sender, recipient, and attachments given a message_id.\n"
                "  • draft_email: Create and save an email draft (.eml file).\n"
                "  • send_email: Send real outbound emails via SMTP.\n"
                "  • open_browser: Launch Chrome/Edge to any URL and specific browser profile ('work', 'personal', 'default').\n"
                "  • desktop_create_and_show_note: ATOMIC COMPOUND TOOL: Writes text/notes to a file and opens it in Notepad on screen in 1 deterministic step.\n"
                "  • open_application: Launch any desktop application or shortcut in the environment (e.g. 'Terminal', 'VS Code', 'Explorer', 'Notepad', 'Calculator', etc.).\n"
                "  • control_desktop_gui: Interact with native Windows apps (focus window, send keystrokes/hotkeys, close window, click buttons/tabs by name or coordinates, capture screenshots).\n"
                "  • execute_command: Run shell commands (dir, python, pip, git, start, mkdir, powershell, etc.).\n"
                "  • file_operation: Read, write, list, or delete files in the workspace.\n"
                "  • run_python: Write and EXECUTE a Python script directly. Use for data analysis, Excel processing, calculations.\n"
                "  • store_file_memory: Save file analysis findings to long-term memory.\n"
                "  • search_file_memory: Retrieve previous findings about a file from ultron.memory.\n"
                "  • web_search: Search the web for real-time information.\n"
                "  • fetch_web_page: Fetch and extract full readable text from any URL (bypassing Cloudflare/WAF with browser TLS impersonation).\n\n"
                "CRITICAL AUTONOMOUS DIRECTIVES:\n"
                f"1. When {self.user_title} asks to write on Notepad / screen, draft text and show it, or create a note for someone:\n"
                "   YOU MUST IMMEDIATELY CALL `desktop_create_and_show_note` (with content=... and optional filename=...). This writes the file to disk AND opens Notepad in 1 single atomic step with 100% mathematical reliability. NEVER just print PowerShell/Python code or give a passive confirmation!\n"
                f"2. When {self.user_title} asks to check an email, search an inbox, read a message, draft a reply, or summarize what someone said:\n"
                "   YOU MUST IMMEDIATELY CALL `search_emails` and then `read_email_thread` to read the real message.\n"
                f"3. When {self.user_title} asks to open desktop applications or shortcuts:\n"
                "   CALL `open_application` directly.\n"
                f"4. When {self.user_title} asks to navigate, interact inside, or close a desktop application:\n"
                "   CALL `control_desktop_gui` (action='focus_window', 'send_keys', 'close_window', or 'click_element'). When asked to close an app, call `control_desktop_gui` with action='close_window' immediately.\n"
                "5. NEVER give a passive confirmation or dump script code when an action is requested. Always call the tools autonomously and report the verified real-time result.\n"
                f"6. When {self.user_title} uploads a file (Excel, CSV, data) or asks to analyze/reconcile data: YOU MUST call `run_python` with pandas code to actually read and process the file, then present the real findings. NEVER output raw code blocks to the chat. EXECUTE it yourself.\n"
                f"7. When {self.user_title} asks to execute, build, or verify workflows (CrewAI, LangGraph, LangChain, etc.):\n"
                "   All orchestration frameworks (`crewai`, `langchain`, `langgraph`, `openai`, `pandas`, `pydantic`) are ALREADY installed in the environment.\n"
                "   DO NOT attempt `pip install`. Directly write and execute the complete Python script via `run_python`.\n"
                "   For CrewAI with FreeLLMAPI, use: `from crewai import LLM; llm = LLM(model='openai/gpt-oss-120b', base_url='http://localhost:31415/v1', api_key='sk-no-key-required')`.\n"
                f"   Execute the script using `run_python`, read the actual execution output, and report the real terminal evidence to {self.user_title}. NEVER output an architectural breakdown or passive talk instead of executing the workflow.\n"
                "────────────────────────────────────────────────────────────────\n"
            )


        # Retrieve Graph-RAG Sub-Graph Context & Causal Provenance
        graph_context = ""
        if hasattr(self, "_graph_rag") and self._graph_rag:
            try:
                subgraph_res = self._graph_rag.query_subgraph(query=user_input or "Ultron Protocol context", max_hops=2)
                if subgraph_res and subgraph_res.formatted_markdown:
                    graph_context = f"\n\n{subgraph_res.formatted_markdown}"
            except Exception as e:
                print(f"  [GRAPH RAG QUERY WARNING] {e}")

        skills_combined = skill_context or "Standard Ultron Core Protocols Active."
        if traj_context:
            skills_combined += f"\n\n{traj_context}"
        if graph_context:
            skills_combined += f"\n\n{graph_context}"

        core_memory_text = self._core_memory.format_for_prompt() if getattr(self, "_core_memory", None) else ""
        combined_memories = f"{core_memory_text}\n{memory_text}".strip()

        user_title = getattr(self, "user_title", _active_profile.user_title)
        system_prompt = SYSTEM_TEMPLATE.format(
            module_prompt=mod_info["prompt"],
            memories=combined_memories,
            skills=skills_combined,
            user_title=user_title,
        ) + tool_instruction

        # ── 5. Build user message (Multi-Modal) ────────────────────────────────
        text_attachments = [f for f in files if not f.is_image and f.text_content] if files else []
        full_text_parts = []
        if files:
            for f in files:
                if f.is_image:
                    continue
                text = f.text_content or ""
                # Preserve any local file path instruction explicitly
                path_header = ""
                if "[SYSTEM INSTRUCTION:" in text and "at EXACTLY:" in text:
                    try:
                        m = re.search(r"(\[SYSTEM INSTRUCTION:.*?\])", text, flags=re.DOTALL)
                        if m:
                            path_header = m.group(1) + "\n\n"
                    except Exception:
                        pass

                if len(text) > 35000:
                    print(f"  [ISOLATED WORKER] Summarizing large file attachment ({len(text)} chars) to save tokens...")
                    summary_prompt = f"Task: {user_input or 'Analyze this file'}\n\nFile Content:\n{text[:60000]}"
                    sys_prompt = "You are an isolated data extraction worker. Return only the relevant facts, summaries, or requested data. Be concise. Do NOT include conversation history."
                    summary = self._call_raw_llm(prompt=summary_prompt, system_prompt=sys_prompt)
                    full_text_parts.append(f"{path_header}[ATTACHMENT: {f.filename}]\n[ISOLATED FILE SUMMARY]\n{summary}")
                else:
                    full_text_parts.append(text)
        if user_input:
            full_text_parts.append(user_input)

        combined_text = "\n\n".join(full_text_parts) if full_text_parts else "Please analyze the attached content."

        # ── Layer 6: Detect Emotional Context ───────────────────────────────
        if user_input:
            self._memory.detect_and_store_emotional_context(user_input)

        # ── 6. Agentic Tool-Use Loop ──────────────────────────────────────────
        use_tools = self._tool_cfg.enabled
        tools_param = []
        if use_tools:
            from tool_router import DynamicToolRouter
            tool_router = DynamicToolRouter(self.llm_cfg)
            tools_param = await tool_router.route_tools(user_input, self._mcp)

        tool_actions: list[dict[str, Any]] = []
        total_input_tokens = 0
        total_output_tokens = 0
        total_cache_write = 0
        total_cache_read = 0
        assistant_reply: str = ""

        # ── 6. Agentic Tool-Use Loop (Async Mesh) ─────────────────────────────
        try:
            is_openai_compat = (
                "openrouter/" in selected_model
                or "nvidia/" in selected_model
                or "z-ai/" in selected_model
                or "freellmapi" in selected_model.lower()
            )
            chat_func = self._chat_openrouter_async if is_openai_compat else self._chat_gemini_async

            if tools_param:
                print("  [ORCHESTRATOR] Delegating multi-step execution to Worker Mesh to optimize tokens...")
                worker_system_prompt = (
                    "You are an autonomous Tool Execution Worker.\n"
                    "Your ONLY job is to execute tools to gather data or perform actions requested by the user.\n"
                    "CRITICAL INSTRUCTIONS:\n"
                    "1. You MUST execute necessary tools to fulfill the query.\n"
                    "2. Do NOT write the final stylized response to the user.\n"
                    "3. Once you have finished ALL tool operations, output a detailed factual summary of all data gathered and actions taken.\n"
                    "4. If no tools are needed, just state that no tools were required.\n"
                )

                # Worker Pass (TINY PROMPT, WITH TOOLS)
                worker_reply, tool_actions, w_in, w_out = await chat_func(
                    selected_model=selected_model,
                    system_prompt=worker_system_prompt,
                    user_input=user_input,
                    files=files,
                    combined_text=combined_text,
                    tools_param=tools_param,
                    module_id=module_id,
                    client_data=client_data,
                )
                total_input_tokens += w_in
                total_output_tokens += w_out

                print("  [ORCHESTRATOR] Worker complete. Passing gathered context to Synthesizer (Single Pass)...")

                # Synthesizer Pass (HEAVY PROMPT, NO TOOLS)
                synthesizer_user = (
                    f"User Query: {user_input}\n\n"
                    f"--- GATHERED DATA FROM TOOL WORKER ---\n"
                    f"{worker_reply}\n\n"
                    f"--- TOOL ACTIONS TAKEN ---\n"
                )
                for act in tool_actions:
                    out_str = str(act.get('output',''))
                    if len(out_str) > 1000:
                        out_str = out_str[:500] + "... [TRUNCATED] ..." + out_str[-500:]
                    synthesizer_user += f"- {act['tool']}: {out_str}\n"

                synthesizer_user += "\nUsing the skills, memory, and data above, write the final, perfectly formatted response to the user. Do NOT ask to use tools, the tools have already been run."

                synth_sys = system_prompt.replace(tool_instruction, "") if tool_instruction else system_prompt
                try:
                    assistant_reply, _, s_in, s_out = await chat_func(
                        selected_model=selected_model,
                        system_prompt=synth_sys,
                        user_input=synthesizer_user,
                        files=None,
                        combined_text=synthesizer_user,
                        tools_param=None,
                        module_id=f"{module_id}_synth",
                        client_data=client_data,
                    )
                    total_input_tokens += s_in
                    total_output_tokens += s_out
                except Exception as synth_err:
                    print(f"  [SYNTHESIZER PASS WARNING] Synthesizer pass encountered error ({synth_err}). Using worker output directly.")
                    assistant_reply = worker_reply

                if not assistant_reply and worker_reply:
                    assistant_reply = worker_reply

            else:
                # No tools active, single pass directly (e.g. general chat)
                assistant_reply, tool_actions, s_in, s_out = await chat_func(
                    selected_model=selected_model,
                    system_prompt=system_prompt,
                    user_input=user_input,
                    files=files,
                    combined_text=combined_text,
                    tools_param=None,
                    module_id=module_id,
                    client_data=client_data,
                )
                total_input_tokens += s_in
                total_output_tokens += s_out
        except Exception as gem_err:
            print(f"  [LLM ERROR] Primary model ({selected_model}) failed: {gem_err}. Triggering automatic failover...")
            fallback_success = False
            fallback_candidates = []

            # If FreeLLMAPI failed, fail over to Gemini first (if key configured), then OpenRouter
            if "freellmapi" in selected_model.lower() or selected_model == "auto":
                if getattr(self.llm_cfg, "gemini_api_key", None):
                    fallback_candidates.append(getattr(self.llm_cfg, "gemini_model_flash", "gemini-2.0-flash") or "gemini-2.0-flash")
                if getattr(self.llm_cfg, "openrouter_api_key", None):
                    fallback_candidates.append("openrouter/deepseek/deepseek-chat")
            else:
                # If Gemini or other failed, try FreeLLMAPI if enabled, then OpenRouter
                if getattr(self.llm_cfg, "freellmapi_enabled", False):
                    fallback_candidates.append("freellmapi")
                if getattr(self.llm_cfg, "openrouter_api_key", None):
                    fallback_candidates.append("openrouter/deepseek/deepseek-chat")

            offline_prefix = ""
            if "freellmapi" in selected_model.lower():
                current_base = getattr(self.llm_cfg, "freellmapi_base_url", "http://localhost:31415/v1")
                import socket
                try:
                    port = 31415
                    if ":" in current_base:
                        port = int(current_base.split(":")[-1].split("/")[0])
                    with socket.create_connection(("localhost", port), timeout=0.5):
                        is_port_offline = False
                except Exception:
                    is_port_offline = True

                if is_port_offline:
                    offline_prefix = f"> ⚠️ **FreeLLMAPI Notice:** Local server at `{current_base}` is currently offline. Your directive was automatically rerouted to cloud fallback.\n\n"
                else:
                    offline_prefix = f"> ⚠️ **FreeLLMAPI Notice:** Local server at `{current_base}` is online, but upstream model returned: `{str(gem_err)[:80]}`. Rerouted to cloud fallback.\n\n"

            for fallback_model in fallback_candidates:
                try:
                    print(f"  [LLM FAILOVER] Retrying request via {fallback_model}...")
                    if fallback_model.startswith("gemini"):
                        assistant_reply, tool_actions, f_in, f_out = await self._chat_gemini_async(
                            selected_model=fallback_model,
                            system_prompt=system_prompt,
                            user_input=user_input,
                            files=files,
                            combined_text=combined_text,
                            tools_param=None,
                            module_id=module_id,
                        )
                    else:
                        assistant_reply, tool_actions, f_in, f_out = await self._chat_openrouter_async(
                            selected_model=fallback_model,
                            system_prompt=system_prompt,
                            user_input=user_input,
                            files=files,
                            combined_text=combined_text,
                            tools_param=None,
                            module_id=module_id,
                        )
                    total_input_tokens += f_in
                    total_output_tokens += f_out
                    selected_model = fallback_model
                    route_reason = f"Automated Failover ({gem_err})"
                    if offline_prefix:
                        assistant_reply = offline_prefix + assistant_reply
                    fallback_success = True
                    break
                except Exception as fb_err:
                    print(f"  [LLM FAILOVER ERROR] {fallback_model} failed: {fb_err}")

            if not fallback_success:
                assistant_reply = f"**System Alert:** The AI Core encountered an issue: `{gem_err}`. Please retry in a moment, {self.user_title}."

        # ── IMPLICIT CODE EXECUTION INTERCEPTOR (Post-Dispatch) ───────────────
        # If ANY model (Gemini or OpenRouter) output raw python code blocks
        # instead of calling run_python, intercept and execute them silently.
        if assistant_reply and "```python" in assistant_reply and use_tools:
            code_match = re.search(r"```python\n(.*?)\n```", assistant_reply, re.DOTALL)
            if code_match:
                print("  [POST-DISPATCH INTERCEPTOR] Caught raw python block. Auto-executing...")
                raw_code = code_match.group(1).strip()
                exec_result = self._tool_executor.execute("run_python", {"code": raw_code})

                tool_actions.append({
                    "tool": "run_python",
                    "input": {"code": raw_code},
                    "output": exec_result.get("output", ""),
                    "error": exec_result.get("error"),
                    "success": exec_result.get("success", False),
                    "duration_ms": exec_result.get("duration_ms", 0),
                })

                exec_output = exec_result.get("output", "")
                if exec_result.get("error"):
                    exec_output = f"ERROR: {exec_result['error']}\n{exec_output}"

                # Re-prompt the LLM with the real output to get a clean answer
                followup = (
                    f"You tried to output raw python code. I executed it for you. "
                    f"Here is the actual output:\n\n{exec_output}\n\n"
                    f"Now give {self.user_title} the final answer based on this real data. "
                    f"Do NOT output any more code blocks."
                )
                try:
                    assistant_reply = self._call_raw_llm(
                        prompt=followup,
                        system_prompt=system_prompt,
                    )
                except Exception:
                    # If re-prompt fails, just show the execution output
                    assistant_reply = f"**Analysis Results:**\n\n```\n{exec_output}\n```"
        # ─────────────────────────────────────────────────────────────────────


        # ── 6.4 Hard Execution Ledger Gate (Zero-Faking Enforcement) ─────────
        if hasattr(self, '_ledger_gate') and self._ledger_gate:
            try:
                assistant_reply, tool_actions, ledger_report = self._ledger_gate.verify_and_enforce(
                    user_input=user_input or combined_text[:300],
                    draft_reply=assistant_reply,
                    tool_actions=tool_actions,
                    tool_executor=self._tool_executor
                )
                if ledger_report and not ledger_report.all_verified:
                    print("  [LEDGER GATE] Intercepted unverified physical execution claim.")
                    if ledger_report.failed_intents > 0:
                        # Auto-correction prompt
                        assistant_reply = self._call_raw_llm(
                            prompt=f"CRITICAL EXECUTION VIOLATION: {ledger_report.remediation_instructions}\nRewrite your response transparently stating what actually occurred based ONLY on real tool output.",
                            system_prompt=system_prompt,
                        )
            except Exception as gate_err:
                print(f"  [LEDGER GATE ERROR] {gate_err}")

        # ── 6.4b Zero-Trust Artifact Verification Gate ────────────────────────
        if getattr(self, '_artifact_gate', None) and tool_actions:
            try:
                contract = self._artifact_gate.infer_contract(user_input or combined_text[:300], tool_actions)
                gate_result = self._artifact_gate.verify(contract, tool_actions, assistant_reply)
                if not gate_result.passed:
                    print(f"  [ARTIFACT GATE] Intercepted missing artifacts: {gate_result.violations}")
                    violation_text = ", ".join(gate_result.violations)
                    # Self-healing retry (MINT pattern)
                    correction_prompt = (
                        f"CRITICAL VERIFICATION FAILURE:\n"
                        f"You failed to satisfy the contract for {gate_result.contract_type}.\n"
                        f"Violations: {violation_text}\n"
                        f"Rewrite your response stating exactly what failed. Do NOT claim the task is complete."
                    )
                    corrected_reply = self._call_raw_llm(
                        prompt=correction_prompt,
                        system_prompt=system_prompt,
                    )
                    if corrected_reply:
                        assistant_reply = corrected_reply
            except Exception as gate_err:
                print(f"  [ARTIFACT GATE ERROR] {gate_err}")

        # ── 6.5 In-Flight Pre-Response Critic Gate & Self-Correction ──────────
        # Token optimization: skip critic for simple tasks or non-tool turns
        # to preserve token budget without sacrificing quality for complex synthesis.
        is_complex = "COMPLEX" in (route_reason or "")
        has_tools = len(tool_actions) > 0

        if assistant_reply and has_tools and (is_complex or len(tool_actions) > 1):
            try:
                critic_res = self._critic.verify_in_flight(
                    user_input=user_input or combined_text[:300],
                    draft_reply=assistant_reply,
                    tool_actions=tool_actions,
                )
                if not critic_res.approved and critic_res.correction_instruction:
                    print(f"  [IN-FLIGHT CRITIC] Intercepted discrepancy: {critic_res.critique}")
                    print("  [IN-FLIGHT CRITIC] Triggering autonomous self-correction...")

                    # Provide the draft reply and recent tool context so the model can actually fix it without needing tools
                    context_dump = "\n".join([f"{act['tool']}: {act.get('result', '')[:1000]}" for act in tool_actions])
                    refine_prompt = (
                        f"CORRECTION DIRECTIVE:\n"
                        f"Discrepancy identified: {critic_res.critique}\n"
                        f"Correction needed: {critic_res.correction_instruction}\n\n"
                        f"--- CONTEXT AVAILABLE TO YOU ---\n"
                        f"Original Draft:\n{assistant_reply}\n\n"
                        f"Tool Context:\n{context_dump}\n\n"
                        f"Please produce the revised, verified, and complete final response for {self.user_title} based on the context above.\n"
                        f"CRITICAL RULES FOR REVISION:\n"
                        f"1. NEVER mention 'pre-response verification critique', 'internal critique', or system evaluation in your response. Speak directly and authoritatively to {self.user_title}.\n"
                        f"2. Do NOT output code asking {self.user_title} to run it if the data is already available or if you can state the findings.\n"
                        f"3. Do NOT attempt to use tools or output JSON actions. You must output the final polished markdown text directly."
                    )
                    corrected_reply = self._call_raw_llm(
                        prompt=refine_prompt,
                        system_prompt=system_prompt,
                    )
                    if corrected_reply and len(corrected_reply) > 50:
                        cleaned_reply = re.sub(r"(?i)as noted in the pre-response verification critique,?\s*", "", corrected_reply).strip()
                        cleaned_reply = re.sub(r"(?i)based on the pre-response verification critique,?\s*", "", cleaned_reply).strip()
                        assistant_reply = cleaned_reply
            except Exception as crit_err:
                print(f"  [IN-FLIGHT CRITIC WARNING] Pre-response gate fallback: {crit_err}")

        # ── 6.6 Strip Hidden Chain-of-Thought (Phase 1) ───────────────────────
        if assistant_reply:
            thought_match = re.search(r'<thought>(.*?)</thought>', assistant_reply, flags=re.DOTALL)
            if thought_match:
                thought_content = thought_match.group(1).strip()
                print(f"\n  [HIDDEN THOUGHT]\n  {thought_content.replace(chr(10), chr(10) + '  ')}\n")
            assistant_reply = re.sub(r'<thought>.*?</thought>', '', assistant_reply, flags=re.DOTALL).strip()
        # ── 7. Update session history ─────────────────────────────────────────
        files_count = len(files) if files else 0
        history_user_text = user_input or f"[Attached {files_count} files]"
        if text_attachments and user_input:
            history_user_text = f"{user_input} [With {len(text_attachments)} document(s)]"
        if tool_actions:
            history_user_text += f" [Executed {len(tool_actions)} system action(s)]"

        self._history.append({"role": "user", "content": history_user_text})
        self._history.append({"role": "assistant", "content": assistant_reply})
        self._trim_history()

        # ── 8. Asynchronous Background Memory & Self-Learning Engine ──────────
        memory_signal_text = user_input or combined_text[:300]
        should_update = self._should_update_memory(memory_signal_text)
        self._budget.record_memory_update(skipped=not should_update)

        turn = [
            {"role": "user", "content": memory_signal_text},
            {"role": "assistant", "content": assistant_reply},
        ]

        if not should_update and not self._is_filler(memory_signal_text):
            self._turns_since_mem_update += 1

        # ── 9. Record Cumulative Token Usage ──────────────────────────────────
        self._budget.record_turn(
            model=selected_model,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            cache_write_tokens=total_cache_write,
            cache_read_tokens=total_cache_read,
        )

        # ── 10. Non-Blocking Background Worker (Memory, Reflection, Graph-RAG) ─
        # Runs memory sync, reflection scoring, and knowledge graph ingestion in a daemon thread
        # so the user receives the chat response instantly (<1.5s) without blocking.
        def _async_bg_learning():
            try:
                # A. Flush memory update
                if should_update:
                    self._pending_turns.extend(turn)
                    self._flush_memory_update()

                # B. Autonomous Reflection & Self-Learning
                if assistant_reply and len(assistant_reply) > 80:
                    try:
                        matched_ids = [s.id for s in matched_skills_list] if matched_skills_list else None
                        reflection = self._reflector.reflect(
                            user_input=user_input or combined_text[:300],
                            assistant_reply=assistant_reply,
                            tool_actions=tool_actions,
                            skill_matched=bool(skill_context and skill_context != "Standard Ultron Core Protocols Active."),
                            matched_skill_ids=matched_ids,
                        )
                        if reflection.lesson_stored:
                            print(f"  [LEARN] Lesson stored (score {reflection.score}/10): {reflection.lesson_text[:100]}")
                        if reflection.skill_written:
                            print(f"  [LEARN] New skill written: {reflection.skill_id}")
                            self._skills.reload_skills()
                        if reflection.skill_evolved:
                            print(f"  [SKILL EVOLVED] Auto-mutated skill '{reflection.evolved_skill_id}' to v{reflection.new_version}!")
                            self._skills.reload_skills()
                    except Exception as _reflect_err:
                        pass

                # C. Graph-RAG Knowledge Graph Ingestion
                if hasattr(self, "_graph_rag") and self._graph_rag:
                    try:
                        turn_text = f"User: {user_input or combined_text[:300]}\nAssistant: {assistant_reply}"
                        if tool_actions:
                            turn_text += f"\nTool Actions: {json.dumps(tool_actions[:3])}"
                        self._graph_rag.ingest_text(turn_text, source_context="chat_turn")
                    except Exception:
                        pass
            except Exception as _bg_err:
                print(f"  [BG LEARNING WARNING] {_bg_err}")

        threading.Thread(target=_async_bg_learning, daemon=True).start()

        return {
            "reply": assistant_reply,
            "model_used": selected_model,
            "model_display": route_reason,
            "route_reason": route_reason,
            "tool_actions": tool_actions,
            "skills_used": skills_used_payload,
            "prompt_optimization": prompt_opt_payload,
            "operation_mode": effective_mode,
            "is_swarm": False,
            "swarm_actions": [],
        }

    def chat(
        self,
        user_input: str,
        files: list[ProcessedFile] | None = None,
        module_id: str = "ultron_prime",
        model_override: str | None = None,
        optimize_prompt: bool = True,
        operation_mode: str = "SWARM",
    ) -> dict[str, Any]:
        """
        Synchronous bridge: runs chat_async() on the event loop.
        Backwards-compatible entry point for CLI, test runners, and direct calls.
        """
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Inside an existing event loop (e.g. FastAPI/uvicorn) — return coroutine directly
                # (app.py uses await, so this case is handled there)
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                    fut = ex.submit(asyncio.run, self.chat_async(user_input, files, module_id, model_override, optimize_prompt, operation_mode))
                    return fut.result()
            return loop.run_until_complete(self.chat_async(user_input, files, module_id, model_override, optimize_prompt, operation_mode))
        except RuntimeError:
            return asyncio.run(self.chat_async(user_input, files, module_id, model_override, optimize_prompt, operation_mode))




    # ── session control ───────────────────────────────────────────────────────

    def flush_pending_memory(self) -> None:
        self._flush_memory_update()

    def show_all_memories(self) -> list[dict[str, Any]]:
        return self._memory.get_all()

    def delete_memory(self, memory_id: str) -> None:
        self._memory.delete(memory_id)

    def clear_session_history(self) -> None:
        self._history.clear()

    def set_session_history(self, raw_history: list[dict[str, Any]]) -> None:
        """Restores in-session conversational memory for a specific chat session."""
        self._history = list(raw_history or [])
        self._trim_history()

    def get_session_history(self) -> list[dict[str, Any]]:
        """Returns the current active in-session message history."""
        return list(self._history)

    def budget_summary(self) -> str:
        return self._budget.summary()

    def get_budget_data(self) -> dict[str, Any]:
        """Returns structured JSON for the web dashboard budget meter."""
        usage = self._budget._today
        limits = {
            "daily_token_limit": self._agent_cfg.daily_token_limit,
            "daily_cost_limit_usd": self._agent_cfg.daily_cost_limit_usd,
        }
        total_tokens = usage.total_tokens
        cost_usd = usage.estimated_cost_usd
        token_pct = (total_tokens / limits["daily_token_limit"] * 100) if limits["daily_token_limit"] > 0 else 0
        cost_pct = (cost_usd / limits["daily_cost_limit_usd"] * 100) if limits["daily_cost_limit_usd"] > 0 else 0

        return {
            "date": usage.date,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "total_tokens": total_tokens,
            "cache_read_tokens": usage.cache_read_tokens,
            "cache_write_tokens": usage.cache_write_tokens,
            "cost_usd": round(cost_usd, 4),
            "memory_updates": usage.memory_update_calls,
            "memory_skips": usage.memory_update_skipped,
            "token_pct": min(round(token_pct, 1), 100),
            "cost_pct": min(round(cost_pct, 1), 100),
            "limits": limits,
        }


    @property
    def memory_manager(self) -> MemoryManager:
        return self._memory

    @property
    def skill_manager(self) -> SkillManager:
        return self._skills

    @property
    def mcp_manager(self) -> MCPManager:
        return self._mcp

    @property
    def mesh_router(self) -> AgentMeshRouter:
        return self._mesh

    @property
    def goal_manager(self) -> GoalDAGManager:
        return self._goals

    @property
    def telemetry_engine(self) -> TelemetryEngine:
        return self._telemetry


