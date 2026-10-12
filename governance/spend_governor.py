"""
governance/spend_governor.py — Financial Budget Sentinel & Token Cost Governor.

Provides:
  1. Centralized tracking of token usage (prompt, completion, cache) and USD expenditure
     per turn, per session, and per task run.
  2. Model cost lookup table (cost per 1M tokens) for Claude, OpenAI, Gemini, DeepSeek, and local models.
  3. Configurable hard caps (e.g. max $0.50 or 50,000 tokens per session run).
  4. Structured BudgetExceededException halting execution when caps are breached.
  5. Graceful transition helper into a terminal summary state rather than crashing.
"""

from __future__ import annotations

import copy
import time
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from core.log_config import get_logger

# ── Model Cost Table (USD per 1M Tokens) ──────────────────────────────────────

MODEL_COST_TABLE: dict[str, dict[str, float]] = {
    # Anthropic Claude
    "claude-3-5-sonnet": {"input": 3.00, "output": 15.00, "cache_write": 3.75, "cache_read": 0.30},
    "claude-3-7-sonnet": {"input": 3.00, "output": 15.00, "cache_write": 3.75, "cache_read": 0.30},
    "claude-sonnet":     {"input": 3.00, "output": 15.00, "cache_write": 3.75, "cache_read": 0.30},
    "claude-3-5-haiku":  {"input": 1.00, "output": 5.00,  "cache_write": 1.25, "cache_read": 0.10},
    "claude-haiku":      {"input": 1.00, "output": 5.00,  "cache_write": 1.25, "cache_read": 0.10},
    "claude-3-opus":     {"input": 15.00, "output": 75.00, "cache_write": 18.75, "cache_read": 1.50},
    "claude-opus":       {"input": 15.00, "output": 75.00, "cache_write": 18.75, "cache_read": 1.50},

    # OpenAI
    "gpt-4o":            {"input": 2.50, "output": 10.00, "cache_write": 2.50, "cache_read": 1.25},
    "gpt-4o-mini":       {"input": 0.15, "output": 0.60,  "cache_write": 0.15, "cache_read": 0.075},
    "o1":                {"input": 15.00, "output": 60.00, "cache_write": 15.00, "cache_read": 7.50},
    "o3-mini":           {"input": 1.10, "output": 4.40,  "cache_write": 1.10, "cache_read": 0.55},

    # Google Gemini
    "gemini-2.0-flash":  {"input": 0.10, "output": 0.40,  "cache_write": 0.00, "cache_read": 0.00},
    "gemini-1.5-flash":  {"input": 0.075, "output": 0.30, "cache_write": 0.00, "cache_read": 0.00},
    "gemini-1.5-pro":    {"input": 1.25, "output": 5.00,  "cache_write": 0.00, "cache_read": 0.00},
    "gemini":            {"input": 0.10, "output": 0.40,  "cache_write": 0.00, "cache_read": 0.00},

    # DeepSeek / Open / Local
    "deepseek-chat":     {"input": 0.14, "output": 0.28,  "cache_write": 0.14, "cache_read": 0.014},
    "deepseek-reasoner": {"input": 0.55, "output": 2.19,  "cache_write": 0.55, "cache_read": 0.14},
    "deepseek":          {"input": 0.14, "output": 0.28,  "cache_write": 0.00, "cache_read": 0.00},
    "local":             {"input": 0.00, "output": 0.00,  "cache_write": 0.00, "cache_read": 0.00},
}


def lookup_model_rates(model_name: str) -> dict[str, float]:
    """Resolves pricing rates per 1M tokens for a given model string."""
    name_lower = (model_name or "").lower()
    for key, rates in MODEL_COST_TABLE.items():
        if key in name_lower:
            return rates
    # Default fallback: Claude 3.5 Sonnet rates
    return MODEL_COST_TABLE["claude-sonnet"]


def calculate_cost_usd(
    model_name: str,
    input_tokens: int,
    output_tokens: int,
    cache_write_tokens: int = 0,
    cache_read_tokens: int = 0,
) -> float:
    """Calculates dollar expenditure based on token counts and model pricing."""
    rates = lookup_model_rates(model_name)
    cost = (
        (input_tokens / 1_000_000.0) * rates["input"]
        + (output_tokens / 1_000_000.0) * rates["output"]
        + (cache_write_tokens / 1_000_000.0) * rates.get("cache_write", 0.0)
        + (cache_read_tokens / 1_000_000.0) * rates.get("cache_read", 0.0)
    )
    return round(cost, 6)


# ── Contracts & Exceptions ───────────────────────────────────────────────────

class BudgetConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    max_cost_usd_per_session: float = 0.50
    max_tokens_per_session: int = 50_000
    max_cost_usd_per_turn: float = 0.15
    max_tokens_per_turn: int = 20_000


class TurnSpendRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    turn_id: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0
    total_tokens: int
    cost_usd: float
    timestamp: float = Field(default_factory=time.time)


class BudgetExceededError(RuntimeError):
    """Raised immediately when an agent task breaches configured spend or token caps."""

    def __init__(
        self,
        session_id: str,
        breach_type: Literal["cost", "tokens"],
        current_val: float,
        limit_val: float,
        model: str,
        message: str | None = None,
    ) -> None:
        unit = "$" if breach_type == "cost" else " tokens"
        msg = message or (
            f"Financial Budget Breach in session '{session_id}': "
            f"current {breach_type} {current_val:.4f}{unit} breached limit {limit_val:.4f}{unit} (Model: {model}). "
            f"Execution halted to prevent financial runaway."
        )
        super().__init__(msg)
        self.session_id = session_id
        self.breach_type = breach_type
        self.current_val = current_val
        self.limit_val = limit_val
        self.model = model

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": "BudgetExceededException",
            "session_id": self.session_id,
            "breach_type": self.breach_type,
            "current_value": self.current_val,
            "limit_value": self.limit_val,
            "model": self.model,
        }

BudgetExceededException = BudgetExceededError


# ── Spend Governor ───────────────────────────────────────────────────────────

class SpendGovernor:
    """
    Centralized financial sentinel tracking cumulative token burn and USD cost.
    Enforces pre-call verification and post-call budget accumulation.
    """

    def __init__(self, config: BudgetConfig | None = None) -> None:
        self.config = config or BudgetConfig()
        self._session_turns: dict[str, list[TurnSpendRecord]] = {}

    def _get_key(self, session_id: str) -> str:
        try:
            from core.auth import current_caller_id
            caller = current_caller_id.get()
            if caller:
                return f'{caller}:{session_id}'
        except ImportError:
            pass
        return session_id

    def get_session_records(self, session_id: str) -> list[TurnSpendRecord]:
        return copy.deepcopy(self._session_turns.get(self._get_key(session_id), []))

    def get_session_totals(self, session_id: str) -> dict[str, Any]:
        records = self._session_turns.get(self._get_key(session_id), [])
        total_tokens = sum(r.total_tokens for r in records)
        total_cost = sum(r.cost_usd for r in records)
        return {
            "session_id": session_id,
            "turn_count": len(records),
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 6),
            "max_cost_usd": self.config.max_cost_usd_per_session,
            "max_tokens": self.config.max_tokens_per_session,
        }

    def assert_within_budget(
        self,
        session_id: str,
        anticipated_tokens: int = 0,
        model: str = "claude-sonnet",
    ) -> None:
        """
        Pre-flight check: ensures current session spend + anticipated usage
        does not breach configured caps.
        """
        totals = self.get_session_totals(session_id)
        current_tokens = totals["total_tokens"]
        current_cost = totals["total_cost_usd"]

        # Check token cap
        projected_tokens = current_tokens + anticipated_tokens
        if projected_tokens > self.config.max_tokens_per_session:
            raise BudgetExceededException(
                session_id=session_id,
                breach_type="tokens",
                current_val=float(projected_tokens),
                limit_val=float(self.config.max_tokens_per_session),
                model=model,
            )

        # Check cost cap
        anticipated_cost = calculate_cost_usd(model, anticipated_tokens, 0)
        projected_cost = current_cost + anticipated_cost
        if projected_cost > self.config.max_cost_usd_per_session:
            raise BudgetExceededException(
                session_id=session_id,
                breach_type="cost",
                current_val=projected_cost,
                limit_val=self.config.max_cost_usd_per_session,
                model=model,
            )

    def record_turn_spend(
        self,
        session_id: str,
        turn_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cache_write_tokens: int = 0,
        cache_read_tokens: int = 0,
    ) -> TurnSpendRecord:
        """
        Records the actual token burn for an LLM turn and enforces post-call caps.
        """
        cost = calculate_cost_usd(
            model_name=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_write_tokens=cache_write_tokens,
            cache_read_tokens=cache_read_tokens,
        )
        total_tokens = input_tokens + output_tokens

        record = TurnSpendRecord(
            turn_id=turn_id,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_write_tokens=cache_write_tokens,
            cache_read_tokens=cache_read_tokens,
            total_tokens=total_tokens,
            cost_usd=cost,
            timestamp=time.time(),
        )

        if self._get_key(session_id) not in self._session_turns:
            self._session_turns[self._get_key(session_id)] = []
        self._session_turns[self._get_key(session_id)].append(record)

        # Enforce budget cap after recording
        self.assert_within_budget(session_id=session_id, model=model)
        return record

    def reset_session(self, session_id: str) -> None:
        """Resets tracked spend for a specific session."""
        if self._get_key(session_id) in self._session_turns:
            del self._session_turns[self._get_key(session_id)]

    def format_terminal_summary(
        self,
        session_id: str,
        exception: BudgetExceededException,
    ) -> dict[str, Any]:
        """
        Builds a graceful terminal state summary response to transition the agent
        cleanly instead of throwing an unhandled crash to the user.
        """
        totals = self.get_session_totals(session_id)
        return {
            "status": "HALTED_BUDGET_EXCEEDED",
            "terminal_state": True,
            "session_id": session_id,
            "error": str(exception),
            "breach_type": exception.breach_type,
            "final_spend_usd": totals["total_cost_usd"],
            "final_tokens": totals["total_tokens"],
            "summary": (
                f"Agent halted gracefully: {exception.breach_type.capitalize()} cap breached "
                f"({totals['total_cost_usd']:.4f}$ / {totals['total_tokens']} tokens). "
                f"Completed {totals['turn_count']} turns before budget exhaustion."
            ),
        }


# Global default governor instance
default_spend_governor = SpendGovernor()

_log = get_logger('spend_governor')
