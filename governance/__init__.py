"""
governance — Phase 4 Spend Caps, Rate Limiting & Resource Exhaustion Protection.

Exports:
  1. SpendGovernor, BudgetExceededException, BudgetConfig, calculate_cost_usd, default_spend_governor
  2. AsyncRateLimiter, ProviderRateLimits, RateLimitQueueTimeoutError, default_rate_limiter
  3. ResourceRegistry, ResourcePool, PoolStarvationError, default_resource_registry
  4. ProcessTracker, BoundedMemoryQueue, BufferOverflowError, default_process_tracker
"""

from governance.spend_governor import (
    BudgetConfig,
    BudgetExceededException,
    SpendGovernor,
    TurnSpendRecord,
    calculate_cost_usd,
    default_spend_governor,
    lookup_model_rates,
)
from governance.rate_limiter import (
    AsyncRateLimiter,
    ProviderRateLimits,
    RateLimitQueueTimeoutError,
    TokenBucket,
    default_rate_limiter,
)
from governance.resource_registry import (
    ManagedResource,
    PoolStarvationError,
    ResourcePool,
    ResourceRegistry,
    default_resource_registry,
)
from governance.process_tracker import (
    BoundedMemoryQueue,
    BufferOverflowError,
    ProcessTracker,
    default_process_tracker,
)
from governance.model_registry import (
    ModelProvider,
    ModelRegistry,
    ModelSpec,
    ModelTier,
    default_model_registry,
)
from governance.db_manager import (
    DatabaseManager,
    default_db_manager,
)

__all__ = [
    # Spend Governor
    "BudgetConfig",
    "BudgetExceededException",
    "SpendGovernor",
    "TurnSpendRecord",
    "calculate_cost_usd",
    "default_spend_governor",
    "lookup_model_rates",
    # Rate Limiter
    "AsyncRateLimiter",
    "ProviderRateLimits",
    "RateLimitQueueTimeoutError",
    "TokenBucket",
    "default_rate_limiter",
    # Resource Registry
    "ManagedResource",
    "PoolStarvationError",
    "ResourcePool",
    "ResourceRegistry",
    "default_resource_registry",
    # Process Tracker
    "BoundedMemoryQueue",
    "BufferOverflowError",
    "ProcessTracker",
    "default_process_tracker",
    # Model Registry
    "ModelProvider",
    "ModelRegistry",
    "ModelSpec",
    "ModelTier",
    "default_model_registry",
    # Database Manager
    "DatabaseManager",
    "default_db_manager",
]
