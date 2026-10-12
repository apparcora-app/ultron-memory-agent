"""
guardrails — Ultron Protocol: In-Flight Verification, Code Sandboxing, and Execution Boundaries.
"""

from ultron.guardrails.ast_sandbox import (
    DANGEROUS_MODULES,
    DEFAULT_SAFE_MODULES,
    ASTSecurityViolation,
    ASTValidator,
)
from ultron.guardrails.critic import (
    CriticResult,
    InFlightCriticGate,
)
from ultron.guardrails.limits import (
    DEFAULT_TOOL_TIMEOUT_SEC,
    MAX_RECURSION_LIMIT,
    ExecutionLimitExceeded,
    RecursionLimiter,
    dispatch_with_timeout,
)

__all__ = [
    "InFlightCriticGate",
    "CriticResult",
    "ASTValidator",
    "ASTSecurityViolation",
    "DEFAULT_SAFE_MODULES",
    "DANGEROUS_MODULES",
    "ExecutionLimitExceeded",
    "RecursionLimiter",
    "dispatch_with_timeout",
    "MAX_RECURSION_LIMIT",
    "DEFAULT_TOOL_TIMEOUT_SEC",
]
