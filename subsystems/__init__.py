"""
subsystems package — Decoupled modular subsystems for the Ultron Agent Architecture.

Provides 4 cohesive subsystems:
- MemorySubsystem: Vector memory, core working memory, Graph-RAG, trajectories, skills
- PlanningSubsystem: Complexity routing, goal DAGs, hierarchical planning, ToT reasoning, prompt optimization
- ExecutionSubsystem: Sandboxing, guarded tool execution, MCP, mesh router, multi-agent swarm
- GovernanceSubsystem: Telemetry, spend limits, execution ledger, critic, reflection, dreaming, model registry, db manager, DLQ
"""

from subsystems.memory import MemorySubsystem
from subsystems.planning import PlanningSubsystem
from subsystems.execution import ExecutionSubsystem
from subsystems.governance import GovernanceSubsystem

__all__ = [
    "MemorySubsystem",
    "PlanningSubsystem",
    "ExecutionSubsystem",
    "GovernanceSubsystem",
]
