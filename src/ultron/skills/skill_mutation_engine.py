"""
skill_mutation_engine.py — Autonomous Skill Mutation & Evolution Engine for Ultron.

Handles automated failure detection, mutation hypothesis synthesis, patch application,
semantic version bumping (v1.0 -> v1.1), and regression testing.
"""

from __future__ import annotations

from ultron.skills.skill_evolution import (
    MutationRecord,
    SkillEvolutionDB,
    SkillMutator,
)

try:
    from skill_manager import SkillManager as AutonomousSkillManager
except ImportError:
    AutonomousSkillManager = Any  # type: ignore

# First-class alias for Skill Mutation Engine
SkillMutationEngine = SkillMutator

__all__ = [
    "SkillMutator",
    "SkillMutationEngine",
    "SkillEvolutionDB",
    "MutationRecord",
    "AutonomousSkillManager",
]
