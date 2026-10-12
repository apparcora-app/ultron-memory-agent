"""
budget_tracker.py — Daily token usage tracking and cost estimation.

Persists usage to ./data/budget.json so limits survive across restarts.
Supports per-model cost tables and Anthropic prompt-cache breakdowns.

Token cost table (per 1M tokens, August 2026):
  claude-haiku-4-5           input $1.00  output $5.00  cache_write $1.25  cache_read $0.10
  claude-sonnet-5-*          input $2.00  output $10.00 cache_write $2.50  cache_read $0.20
  claude-opus-5-*            input $5.00  output $25.00 cache_write $6.25  cache_read $0.50
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from core.log_config import get_logger

# ── cost table ────────────────────────────────────────────────────────────────

_COST_TABLE: dict[str, dict[str, float]] = {
    # key: lowercase model prefix → costs per 1M tokens in USD
    "nvidia":           {"input": 0.00, "output": 0.00, "cache_write": 0.00, "cache_read": 0.00},
    "z-ai":             {"input": 0.00, "output": 0.00, "cache_write": 0.00, "cache_read": 0.00},
    "deepseek":         {"input": 0.14, "output": 0.28, "cache_write": 0.00, "cache_read": 0.00},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40, "cache_write": 0.00, "cache_read": 0.00},
    "gemini":           {"input": 0.10, "output": 0.40, "cache_write": 0.00, "cache_read": 0.00},
    "claude-haiku":     {"input": 1.00, "output": 5.00,  "cache_write": 1.25, "cache_read": 0.10},
    "claude-sonnet":    {"input": 2.00, "output": 10.00, "cache_write": 2.50, "cache_read": 0.20},
    "claude-opus":      {"input": 5.00, "output": 25.00, "cache_write": 6.25, "cache_read": 0.50},
}

def _get_costs(model: str) -> dict[str, float]:
    """Return cost dict for the given model string, defaulting to Sonnet rates."""
    model_lower = model.lower()
    for prefix, costs in _COST_TABLE.items():
        if prefix in model_lower:
            return costs
    return _COST_TABLE["claude-sonnet"]


# ── dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class DayUsage:
    date: str                      = field(default_factory=lambda: str(date.today()))
    input_tokens: int              = 0
    output_tokens: int             = 0
    cache_write_tokens: int        = 0
    cache_read_tokens: int         = 0
    memory_update_calls: int       = 0   # how many Mem0 add() calls were made
    memory_update_skipped: int     = 0   # how many were intelligently skipped
    estimated_cost_usd: float      = 0.0

    def add_turn(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cache_write_tokens: int = 0,
        cache_read_tokens: int = 0,
    ) -> None:
        self.input_tokens       += input_tokens
        self.output_tokens      += output_tokens
        self.cache_write_tokens += cache_write_tokens
        self.cache_read_tokens  += cache_read_tokens
        self.estimated_cost_usd += _calculate_cost(
            model, input_tokens, output_tokens, cache_write_tokens, cache_read_tokens
        )

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def memory_skip_rate(self) -> float:
        total = self.memory_update_calls + self.memory_update_skipped
        return self.memory_update_skipped / total if total else 0.0


def _calculate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_write_tokens: int = 0,
    cache_read_tokens: int = 0,
) -> float:
    c = _get_costs(model)
    return (
        (input_tokens       / 1_000_000) * c["input"]  +
        (output_tokens      / 1_000_000) * c["output"] +
        (cache_write_tokens / 1_000_000) * c["cache_write"] +
        (cache_read_tokens  / 1_000_000) * c["cache_read"]
    )


# ── tracker ───────────────────────────────────────────────────────────────────

class BudgetTracker:
    """
    Tracks daily API usage and enforces a configurable token/cost budget.

    Parameters
    ----------
    daily_token_limit:
        Hard cap on total tokens per day (input + output). 0 = unlimited.
    daily_cost_limit_usd:
        Soft cap on estimated spend per day in USD. 0 = unlimited.
    data_dir:
        Directory to persist budget.json.
    """

    def __init__(
        self,
        daily_token_limit: int = 0,
        daily_cost_limit_usd: float = 0.0,
        data_dir: str = "data",
    ) -> None:
        self.daily_token_limit    = daily_token_limit
        self.daily_cost_limit_usd = daily_cost_limit_usd
        self._path = Path(data_dir) / "budget.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._today: DayUsage = self._load_today()

    # ── persistence ───────────────────────────────────────────────────────────

    def _load_today(self) -> DayUsage:
        today_str = str(date.today())
        if self._path.exists():
            try:
                with open(self._path) as f:
                    data = json.load(f)
                if data.get("date") == today_str:
                    return DayUsage(**data)
            except (json.JSONDecodeError, TypeError):
                pass
        return DayUsage(date=today_str)

    def _save(self) -> None:
        with open(self._path, "w") as f:
            json.dump(asdict(self._today), f, indent=2)

    # ── public API ────────────────────────────────────────────────────────────

    def record_usage(self, input_tokens: int = 0, output_tokens: int = 0, model: str = 'claude-sonnet', cache_write_tokens: int = 0, cache_read_tokens: int = 0) -> None:
        self.record_turn(model, input_tokens, output_tokens, cache_write_tokens, cache_read_tokens)

    def record_turn(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cache_write_tokens: int = 0,
        cache_read_tokens: int = 0,
    ) -> None:
        """Record token usage for one chat turn and persist."""
        # Roll over if day changed mid-session
        if self._today.date != str(date.today()):
            self._today = DayUsage()
        self._today.add_turn(
            model, input_tokens, output_tokens, cache_write_tokens, cache_read_tokens
        )
        self._save()

    def record_memory_update(self, skipped: bool) -> None:
        """Track memory update call vs skip decisions."""
        if self._today.date != str(date.today()):
            self._today = DayUsage()
        if skipped:
            self._today.memory_update_skipped += 1
        else:
            self._today.memory_update_calls += 1
        self._save()

    def check_budget(self) -> tuple[bool, str]:
        """
        Returns (ok, message).
        ok=False means the budget is exhausted — caller should halt.
        """
        if self.daily_token_limit and self._today.total_tokens >= self.daily_token_limit:
            return False, (
                f"Daily token limit reached: {self._today.total_tokens:,} / "
                f"{self.daily_token_limit:,} tokens used."
            )
        if self.daily_cost_limit_usd and self._today.estimated_cost_usd >= self.daily_cost_limit_usd:
            return False, (
                f"Daily cost limit reached: ${self._today.estimated_cost_usd:.4f} / "
                f"${self.daily_cost_limit_usd:.2f} spent."
            )
        return True, ""

    def warn_if_approaching(self, threshold: float = 0.80) -> str | None:
        """Return a warning string when usage crosses `threshold` fraction of the limit."""
        if self.daily_token_limit:
            ratio = self._today.total_tokens / self.daily_token_limit
            if ratio >= threshold:
                return (
                    f"⚠️  Token budget at {ratio:.0%}: "
                    f"{self._today.total_tokens:,} / {self.daily_token_limit:,}"
                )
        if self.daily_cost_limit_usd:
            ratio = self._today.estimated_cost_usd / self.daily_cost_limit_usd
            if ratio >= threshold:
                return (
                    f"⚠️  Cost budget at {ratio:.0%}: "
                    f"${self._today.estimated_cost_usd:.4f} / ${self.daily_cost_limit_usd:.2f}"
                )
        return None


    def get_stats(self) -> dict[str, Any]:
        """Return dictionary of current usage statistics."""
        u = self._today
        return {
            "date": u.date,
            "input_tokens": u.input_tokens,
            "output_tokens": u.output_tokens,
            "total_tokens": u.total_tokens,
            "cache_write_tokens": u.cache_write_tokens,
            "cache_read_tokens": u.cache_read_tokens,
            "estimated_cost_usd": round(u.estimated_cost_usd, 6),
            "memory_update_calls": u.memory_update_calls,
            "memory_update_skipped": u.memory_update_skipped,
            "memory_skip_rate": round(u.memory_skip_rate, 4),
            "daily_token_limit": self.daily_token_limit,
            "daily_cost_limit_usd": self.daily_cost_limit_usd,
        }

    def summary(self) -> str:
        u = self._today
        skip_pct = f"{u.memory_skip_rate:.0%}" if (u.memory_update_calls + u.memory_update_skipped) else "n/a"
        lines = [
            f"📊 Usage for {u.date}",
            f"   Tokens  : {u.input_tokens:,} in  |  {u.output_tokens:,} out",
            f"   Cache   : {u.cache_write_tokens:,} written  |  {u.cache_read_tokens:,} read (saved ${_calculate_cost('claude-sonnet', u.cache_read_tokens, 0):.4f})",
            f"   Cost    : ${u.estimated_cost_usd:.4f} USD (estimated)",
            f"   Memory  : {u.memory_update_calls} updates  |  {u.memory_update_skipped} skipped ({skip_pct} skip rate)",
        ]
        if self.daily_token_limit:
            lines.append(f"   Limit   : {u.total_tokens:,} / {self.daily_token_limit:,} tokens")
        if self.daily_cost_limit_usd:
            lines.append(f"   Budget  : ${u.estimated_cost_usd:.4f} / ${self.daily_cost_limit_usd:.2f}")
        return "\n".join(lines)

_log = get_logger('budget_tracker')
