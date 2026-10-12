"""
agent.py — Convenience alias exposing MemoryAgent from ultron.agent.
"""
import sys
from pathlib import Path

_src_dir = Path(__file__).resolve().parent / "src"
if _src_dir.exists() and str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

from ultron.agent import (  # noqa: E402
    BudgetExceededError,
    MemoryAgent,
    ULTRON_MODULES,
)

__all__ = ["MemoryAgent", "ULTRON_MODULES", "BudgetExceededError"]
