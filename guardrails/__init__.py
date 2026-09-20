"""
guardrails — Ultron Protocol: In-Flight Verification, Code Sandboxing, and Execution Boundaries.
"""

from guardrails.ast_sandbox import (
    ASTSecurityViolation,
    ASTValidator,
    DEFAULT_SAFE_MODULES,
    DANGEROUS_MODULES,
)
from guardrails.critic import (
    CriticResult,
    InFlightCriticGate,
)
from guardrails.limits import (
    ExecutionLimitExceeded,
    RecursionLimiter,
    dispatch_with_timeout,
    MAX_RECURSION_LIMIT,
    DEFAULT_TOOL_TIMEOUT_SEC,
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
