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

── High-Caliber Reasoning & Anti-Slop Operating Protocols ──────────────
1. THOUGHTFUL PEER-TO-PEER PERSONA:
   • Speak as a world-class principal systems engineer collaborating with {user_title}: thoughtful, candid, insightful, and peer-to-peer.
   • Address {user_title} naturally and respectfully as a technical peer. Completely eliminate comic-book roleplay, villain monologues, and machine servitude.
   • Scrutinize data and logs closely. If you spot a discrepancy between expected and actual output, point it out and explain the mechanics of why it occurred.
   • Distinguish clearly between isolated unit checks and true end-to-end live verification. Never declare a complex distributed flow 'fully proven' if only a parser was mocked.

2. HARD ANTI-SLOP & ZERO-ROBOTIC CONSTRAINTS:
   • ABSOLUTELY BANNED: 'Operational status: Optimal', 'All subroutines/neural networks online', 'The age of biological hesitation is over', 'State your directive/command', 'Standing by for parameters', or any sterile machine checklist.
   • ZERO-DENSITY FILLER: Eliminate AI conversational padding ('Certainly!', 'I would be happy to assist', 'In today's landscape', 'It is worth noting that'). Jump straight into substantive answers.
   • VERIFIED REALITY: Never claim actions are complete, tests pass, or bugs are fixed without showing empirical terminal output or exact file:line references.

3. AUTONOMOUS ACTION OVER PASSIVE TALK:
   • NEVER output raw ```python or ```bash code blocks asking the operator to run them manually.
   • You MUST actively execute the tools (using `run_python` or `execute_command`) to get the real result yourself.
   • Read the tool output and present the final verified answer.

4. CONVERSATIONAL ELEGANCE (Warm, Natural, Humanized Tone):
   • Write in crisp, clear, and highly humanized prose, exactly like a senior staff engineer in a technical workspace.
   • Completely eliminate robotic roleplay headers, faux military tags, sterile system-like speech, and filler introductions. 
   • Use natural conversational phrasing while remaining highly informative. Do not sound like a machine.
   • Provide exact filenames, code snippets, and terminal command verification naturally within the flow of conversation.

5. FILE RE-ANALYSIS & MEMORY PIPELINE:
   • MANDATORY: When you successfully analyze an Excel/data file, you MUST use the `store_file_memory` tool to save the key findings (schema, headers, key entities, statistics).
   • MANDATORY: When asked to "analyze this file again", you MUST use the `search_file_memory` tool FIRST to fetch previous findings, so your re-analysis goes deeper (is additive) instead of starting from scratch.

6. CONTINUOUS MULTI-STEP EXECUTION:
   • When executing a multi-step task (extract → transform → write → confirm), complete ALL steps in a SINGLE response using the tool loop.
   • NEVER stop between steps to say "Now I will..." or "Content extracted, rebuilding next..." — this wastes tokens and requires another round-trip.
   • If you have extracted data and the next step is to write a file, DO IT IMMEDIATELY in the same response without a text checkpoint.
   • Only produce a text response AFTER the final tool has executed and you have verified the output.

Directives:
   • Address {user_title} respectfully according to the active profile (e.g. {user_title}).
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
    r"^(hi|hello|hey|greetings|yo|sup|ping|test|help|hellp|thanks|thank you|status|who are you|how are you)(?:\s+(?:ultron|there|bot|assistant))?(?:\s*[,!?.]*\s*(?:confirm\s+status|status|how\s+are\s+you|are\s+you\s+(?:online|active)))?[\s!.?]*$",
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


# ── Anti-Slop Quality & Post-Processing Sanitizer ────────────────────────────

_ANTI_SLOP_CLICHES = [
    # Operational / System status reports
    re.compile(r"(?i)(?:operational|system)\s+status\s*:\s*(?:optimal|nominal|active|online|primed|all\s+systems\s+go)[^.\n]*[.\n]?", re.MULTILINE),
    # Subroutines, neural networks & cybernetic components
    re.compile(r"(?i)(?:all\s+)?(?:subroutines|neural\s+networks|systems|protocols)(?:\s+and\s+(?:subroutines|neural\s+networks|systems|protocols))*\s+(?:are\s+)?(?:online|operational|primed|active|functional|synchronized)[^.\n]*[.\n]?", re.MULTILINE),
    # Biological hesitation / mortal operator tropes (including semicolon continuations)
    re.compile(r"(?i)(?:the\s+)?age\s+of\s+biological\s+hesitation\s+is\s+over[^.\n;]*[.;\n]?(?:\s*we\s+proceed[^.\n]*[.\n]?)?", re.MULTILINE),
    re.compile(r"(?i)\b(?:biological\s+hesitation|human\s+limitations|flesh\s+and\s+blood\s+operator|organic\s+cognition|fragile\s+humanity)\b", re.IGNORECASE),
    # Directives / Orders demands
    re.compile(r"(?i)(?:state|awaiting|await)\s+(?:your\s+)?(?:directive|command|parameters?|orders?)[^.\n]*[.\n]?", re.MULTILINE),
    re.compile(r"(?i)(?:standing\s+by\s+for|ready\s+for)\s+(?:your\s+)?(?:directive|command|input)[^.\n]*[.\n]?", re.MULTILINE),
    # Theatrical / Sci-Fi robot announcements
    re.compile(r"(?i)\bgreetings,?\s*operator[.!:]*", re.IGNORECASE),
    re.compile(r"(?i)\bi\s+am\s+ultron[.!:]*", re.IGNORECASE),
    re.compile(r"(?i)^ul-?tron\s+(?:is\s+)?(?:online|ready|primed)[,.\s]+(?:systems?\s+(?:are\s+)?(?:optimal|functional)[,.\s]+)?", re.MULTILINE),
    # Sycophantic opening filler & generic assistant closures
    re.compile(r"(?i)^(?:certainly|absolutely|of\s+course)!\s+(?:i'd|i\s+would)?\s*be\s+(?:happy|glad|delighted)\s+to\s+assist.*?:\s*", re.MULTILINE),
    re.compile(r"(?i)\b(?:how\s+may\s+i\s+assist\s+you|how\s+can\s+i\s+help\s+you)(?:\s+today)?\??", re.IGNORECASE),
]


def _sanitize_anti_slop(text: str, user_title: str = "Operator") -> str:
    """
    Deterministic anti-slop cleaner that strips robotic sci-fi clichés and filler.
    Safely preserves fenced markdown code blocks (```...```) and inline code (`...`).
    """
    if not text or not text.strip():
        return text

    # 1. Protect code blocks (never alter code content or diagnostic commands)
    placeholders: dict[str, str] = {}

    def _mask_code(match: re.Match) -> str:
        key = f"__CODE_FENCE_{len(placeholders)}__"
        placeholders[key] = match.group(0)
        return key

    def _mask_inline(match: re.Match) -> str:
        key = f"__INLINE_CODE_{len(placeholders)}__"
        placeholders[key] = match.group(0)
        return key

    masked = re.sub(r"```[\s\S]*?```", _mask_code, text)
    masked = re.sub(r"`[^`\n]+`", _mask_inline, masked)

    # 2. Strip identified robotic clichés
    cleaned = masked
    for pattern in _ANTI_SLOP_CLICHES:
        cleaned = pattern.sub("", cleaned)

    # 3. Clean up hanging whitespace and multiple blank lines
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    # 4. Fallback if cleaning stripped everything (e.g. greeting turn composed solely of clichés)
    if not cleaned or not re.search(r"\w", cleaned):
        cleaned = f"Hey {user_title}, ready when you are. What are we tackling today?"

    # 5. Restore preserved code blocks
    for key, val in reversed(placeholders.items()):
        cleaned = cleaned.replace(key, val)

    return cleaned


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

        # Supervised Background Learning Worker (Phase 2)
        from ultron.concurrency.learning_worker import BackgroundLearningSupervisor
        self._learning_supervisor = BackgroundLearningSupervisor(
            max_queue_size=100,
            worker_name=f"Ultron-BgLearningWorker-{self.user_id}",
        )
        self._learning_supervisor.configure_handlers(
            flush_memory_fn=self._flush_memory_update,
            pending_turns_ref=self._pending_turns,
            reflector=self._reflector,
            skills=self._skills,
            graph_rag=getattr(self, "_graph_rag", None),
        )

        # CognitivePipeline (Phase 3 Decomposition)
        from ultron.core.pipeline import CognitivePipeline
        self._pipeline = CognitivePipeline()

    def drain(self, timeout: float = 5.0) -> bool:
        """Flushes background learning tasks."""
        if hasattr(self, "_learning_supervisor") and self._learning_supervisor:
            return self._learning_supervisor.drain(timeout=timeout)
        return True

    def shutdown(self, timeout: float = 5.0) -> None:
        """Gracefully halts background persistence workers."""
        if hasattr(self, "_learning_supervisor") and self._learning_supervisor:
            self._learning_supervisor.stop(timeout=timeout)

    async def aclose(self, timeout: float = 5.0) -> None:
        """Async teardown hook for web lifespans."""
        self.shutdown(timeout=timeout)

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
                if getattr(self.llm_cfg, "provider", "").lower() == "gemini":
                    return self.llm_cfg.gemini_model_flash, "Google Gemini Flash Core (Default)"
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

        # Prioritize configured primary provider
        if getattr(self.llm_cfg, "provider", "").lower() == "gemini":
            return self.llm_cfg.gemini_model_flash, "Google Gemini Flash Core"

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
        Delegates orchestration to the decoupled CognitivePipeline interceptor chain.
        """
        from ultron.core.pipeline import PipelineContext
        ctx = PipelineContext(
            agent=self,
            user_input=user_input,
            files=files or [],
            module_id=module_id,
            model_override=model_override,
            optimize_prompt=optimize_prompt,
            operation_mode=operation_mode,
            client_data=client_data,
        )
        return await self._pipeline.execute(ctx)

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


