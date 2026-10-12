"""
resilience package — Circuit Breakers, Tiered Failover, Retries, and Dead Letter Queue.

Exports:
  1. Circuit Breakers:
     - CircuitState, CircuitBreakerOpenError, CircuitBreakerConfig, CircuitBreaker,
       CircuitBreakerRegistry, default_breaker_registry
  2. Retries & Failover:
     - TRANSIENT_ERROR_PATTERNS, is_transient_error, RetryPolicy, FailoverResult,
       execute_with_retry, ModelProviderCandidate, TieredModelFailover
  3. Dead Letter Queue:
     - DeadLetterRecord, DeadLetterQueue, default_dlq
"""

from ultron.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
    CircuitBreakerRegistry,
    CircuitState,
    default_breaker_registry,
)
from ultron.resilience.dlq import (
    DeadLetterQueue,
    DeadLetterRecord,
    default_dlq,
)
from ultron.resilience.failover import (
    TRANSIENT_ERROR_PATTERNS,
    FailoverResult,
    ModelProviderCandidate,
    RetryPolicy,
    TieredModelFailover,
    create_default_failover_chain,
    execute_with_retry,
    is_transient_error,
)

__all__ = [
    # Circuit Breaker
    "CircuitState",
    "CircuitBreakerOpenError",
    "CircuitBreakerConfig",
    "CircuitBreaker",
    "CircuitBreakerRegistry",
    "default_breaker_registry",
    # Failover & Retries
    "TRANSIENT_ERROR_PATTERNS",
    "is_transient_error",
    "RetryPolicy",
    "FailoverResult",
    "execute_with_retry",
    "ModelProviderCandidate",
    "TieredModelFailover",
    "create_default_failover_chain",
    # DLQ
    "DeadLetterRecord",
    "DeadLetterQueue",
    "default_dlq",
]
