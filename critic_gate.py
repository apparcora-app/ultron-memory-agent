"""
critic_gate.py — Pre-Response In-Flight Verification Critic Gate for Ultron.

Intercepts candidate agent replies before final delivery, running automated verification
to detect hallucinated numbers, unfulfilled tool calls, and severe factual errors.
"""

from __future__ import annotations

from reflection_engine import (
    InFlightCritic,
    CriticResult,
)

# First-class alias for Critic Gate
CriticGate = InFlightCritic
InFlightCriticGate = InFlightCritic

__all__ = [
    "InFlightCritic",
    "CriticResult",
    "CriticGate",
    "InFlightCriticGate",
]
