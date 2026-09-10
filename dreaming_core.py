"""
dreaming_core.py — Autonomous Dreaming & Virtual Simulation Core for Ultron.

Runs offline virtual sandbox simulations over low-scoring memories, synthesizes hypotheses,
executes auto-patches in a safe Python sandbox, and commits winning trajectories to ChromaDB.
"""

from __future__ import annotations

from dreaming_engine import (
    DreamingEngine,
    DreamResult,
    DreamCandidate,
    DreamingDB,
)

# First-class alias for Dreaming Core
DreamingCore = DreamingEngine
AutonomousDreamingCore = DreamingEngine

__all__ = [
    "DreamingEngine",
    "DreamingCore",
    "AutonomousDreamingCore",
    "DreamResult",
    "DreamCandidate",
    "DreamingDB",
]
