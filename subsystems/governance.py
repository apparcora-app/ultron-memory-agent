"""
subsystems/governance.py — Governance, Telemetry & Resilience Subsystem for Ultron Protocol.

Encapsulates all governance, monitoring, budget, security, reflection, and database management:
- TelemetryEngine (Prometheus / structured telemetry)
- BudgetTracker & SpendGovernor (token & financial cap halting)
- ExecutionLedgerGate (physical action verification & zero-faking)
- ArtifactVerificationGate (zero-trust file modification checks)
- InFlightCriticGate (pre-response verification critic)
- ReflectionEngine (autonomous self-learning & skill evolution)
- DreamingEngine (background simulation & offline optimization)
- ModelRegistry (centralized model rotation pools & circuit breaker status)
- DatabaseManager (centralized SQLite WAL management & online backups)
- DeadLetterQueue (DLQ for failed background tasks & upstream outages)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from budget_tracker import BudgetTracker
from config import AgentConfig, LLMConfig, ReflectionConfig
from dreaming_engine import DreamingEngine
from execution_ledger_gate import ExecutionLedgerGate
from governance.db_manager import DatabaseManager, default_db_manager
from governance.model_registry import ModelRegistry, default_model_registry
from governance.spend_governor import SpendGovernor, default_spend_governor
from resilience import DeadLetterQueue, default_dlq
from guardrails import InFlightCriticGate
from reflection_engine import ReflectionEngine
from telemetry import TelemetryEngine

try:
    from artifact_verification_gate import ArtifactVerificationGate
except ImportError:
    ArtifactVerificationGate = None


@dataclass
class GovernanceSubsystem:
    """Cohesive facade managing all governance, telemetry, budget, verification, and resilience components."""
    telemetry: TelemetryEngine
    budget: BudgetTracker
    spend_governor: SpendGovernor
    ledger_gate: ExecutionLedgerGate
    artifact_gate: Optional[Any]
    critic: InFlightCriticGate
    reflector: ReflectionEngine
    dreamer: DreamingEngine
    model_registry: ModelRegistry = default_model_registry
    db_manager: DatabaseManager = default_db_manager
    dlq: DeadLetterQueue = default_dlq

    @classmethod
    def create_default(
        cls,
        agent_cfg: Optional[AgentConfig] = None,
        llm_cfg: Optional[LLMConfig] = None,
        reflection_cfg: Optional[ReflectionConfig] = None,
        claude: Any = None,
        gemini: Any = None,
        provider: str = "gemini",
        telemetry: Optional[TelemetryEngine] = None,
        memory_manager: Any = None,
        trajectories: Any = None,
        skills: Any = None,
    ) -> GovernanceSubsystem:
        """Factory creating the production-grade governance subsystem."""
        agent_cfg = agent_cfg or AgentConfig()
        llm_cfg = llm_cfg or LLMConfig()
        reflection_cfg = reflection_cfg or ReflectionConfig()

        telemetry_engine = telemetry or TelemetryEngine()
        budget = BudgetTracker(
            daily_token_limit=agent_cfg.daily_token_limit,
            daily_cost_limit_usd=agent_cfg.daily_cost_limit_usd,
        )

        ledger_gate = ExecutionLedgerGate()

        artifact_gate = None
        if ArtifactVerificationGate is not None:
            try:
                artifact_gate = ArtifactVerificationGate()
            except Exception:
                artifact_gate = None

        critic = InFlightCriticGate(
            claude=claude,
            gemini=gemini,
            gemini_model=llm_cfg.gemini_model,
            haiku_model=llm_cfg.chat_model_haiku,
            provider=provider,
            enabled=reflection_cfg.enabled,
        )

        skills_dir = skills.skills_dir if skills and hasattr(skills, "skills_dir") else "./skills"
        reflector = ReflectionEngine(
            claude=claude,
            gemini=gemini,
            gemini_model=llm_cfg.gemini_model,
            memory_manager=memory_manager,
            trajectory_manager=trajectories,
            haiku_model=llm_cfg.chat_model_haiku,
            provider=provider,
            skills_dir=skills_dir,
            skill_manager=skills,
            enabled=reflection_cfg.enabled,
            cooldown_turns=reflection_cfg.cooldown_turns,
            max_fail_score=reflection_cfg.max_fail_score,
            min_skill_score=reflection_cfg.min_skill_score,
            auto_skill_prefix=reflection_cfg.auto_skill_prefix,
        )

        dreamer = DreamingEngine(
            claude=claude,
            haiku_model=llm_cfg.chat_model_haiku,
            gemini=gemini,
            gemini_model=llm_cfg.gemini_model,
            provider=provider,
            telemetry=telemetry_engine,
            skill_manager=skills,
            trajectory_manager=trajectories,
            memory_manager=memory_manager,
        )

        return cls(
            telemetry=telemetry_engine,
            budget=budget,
            spend_governor=default_spend_governor,
            ledger_gate=ledger_gate,
            artifact_gate=artifact_gate,
            critic=critic,
            reflector=reflector,
            dreamer=dreamer,
            model_registry=default_model_registry,
            db_manager=default_db_manager,
            dlq=default_dlq,
        )
