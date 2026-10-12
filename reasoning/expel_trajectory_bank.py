"""
expel_trajectory_bank.py — ExpeL (Experience-based Learner) Trajectory Bank for Ultron.

Provides Episodic Experience Storage, Precedent Replay, and Semantic Trajectory Retrieval.
Backed by SQLite (./data/trajectories.db) and ChromaDB (ultron_trajectories).
"""

from __future__ import annotations

from trajectory_manager import (
    EpisodicTrajectory,
    TrajectoryManager,
    TrajectoryStep,
)

# First-class alias for ExpeL Trajectory Bank
ExpeLTrajectoryBank = TrajectoryManager
ExpelTrajectoryBank = TrajectoryManager
TrajectoryBank = TrajectoryManager

__all__ = [
    "EpisodicTrajectory",
    "TrajectoryStep",
    "TrajectoryManager",
    "ExpeLTrajectoryBank",
    "ExpelTrajectoryBank",
    "TrajectoryBank",
]
