"""
critic_gate.py — Pre-Response In-Flight Verification Critic Gate for Ultron.

Intercepts candidate agent replies before final delivery, running automated verification
to detect hallucinated numbers, unfulfilled tool calls, and severe factual errors.
"""

from __future__ import annotations

from ultron.guardrails.critic import (
    CriticResult,
    InFlightCriticGate,
)

# First-class backward compatible aliases
InFlightCritic = InFlightCriticGate
CriticGate = InFlightCriticGate

__all__ = [
    "InFlightCritic",
    "CriticResult",
    "CriticGate",
    "InFlightCriticGate",
]
