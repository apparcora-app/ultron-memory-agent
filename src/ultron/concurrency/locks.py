"""
concurrency/locks.py — Session-Scoped Granular Async Locks & Mutex Manager.

Provides:
  1. Granular key-based async locks (e.g., `session:{session_id}`, `resource:{path}`).
  2. Re-entrant async locks supporting nested calls within the same asyncio.Task or with explicit ownership tokens.
  3. Explicit lock acquisition timeouts (default: 5.0s) to prevent deadlocks and indefinite thread hangs.
  4. Global registry avoiding single-point global lock bottlenecks.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any


class LockAcquisitionTimeoutError(TimeoutError):
    """Raised when acquiring a granular lock exceeds the configured timeout."""

    def __init__(self, resource_key: str, timeout_sec: float) -> None:
        super().__init__(
            f"Failed to acquire lock for resource '{resource_key}' within {timeout_sec:.2f}s. "
            f"Operation aborted to prevent deadlock or hanging state."
        )
        self.resource_key = resource_key
        self.timeout_sec = timeout_sec


class ReentrantAsyncLock:
    """
    An asyncio-compatible lock that supports re-entrancy within the same asyncio.Task
    or matching ownership token.
    """

    def __init__(self, name: str = "unnamed_lock") -> None:
        self.name = name
        self._lock = asyncio.Lock()
        self._owner: Any = None
        self._depth: int = 0

    @property
    def is_locked(self) -> bool:
        return self._lock.locked()

    @property
    def depth(self) -> int:
        return self._depth

    async def acquire(self, timeout: float = 5.0, owner_token: str | None = None) -> bool:
        """
        Acquire the lock with a strict timeout.
        Supports re-entry if requested by the current owning task or matching owner token.
        """
        current_identity = owner_token if owner_token is not None else asyncio.current_task()

        # Re-entrant acquisition
        if self._owner is not None and self._owner == current_identity:
            self._depth += 1
            return True

        # Non-re-entrant / new acquisition with timeout
        try:
            acquired = await asyncio.wait_for(self._lock.acquire(), timeout=timeout)
            if acquired:
                self._owner = current_identity
                self._depth = 1
                return True
            return False
        except asyncio.TimeoutError as err:
            raise LockAcquisitionTimeoutError(self.name, timeout) from err

    def release(self, owner_token: str | None = None) -> None:
        """
        Release the lock. Decrements re-entry depth; truly releases when depth reaches zero.
        """
        current_identity = owner_token if owner_token is not None else asyncio.current_task()

        if self._owner != current_identity:
            raise RuntimeError(
                f"Cannot release lock '{self.name}': caller '{current_identity}' is not the current owner '{self._owner}'."
            )

        self._depth -= 1
        if self._depth == 0:
            self._owner = None
            self._lock.release()

    @asynccontextmanager
    async def hold(self, timeout: float = 5.0, owner_token: str | None = None) -> AsyncIterator[None]:
        """Context manager for acquiring and safely releasing the lock."""
        await self.acquire(timeout=timeout, owner_token=owner_token)
        try:
            yield
        finally:
            self.release(owner_token=owner_token)


class AsyncLockRegistry:
    """
    Registry managing granular per-session and per-resource async locks.
    Never creates a global bottleneck; each resource key receives its own isolated lock.
    """

    def __init__(self) -> None:
        self._locks: dict[str, ReentrantAsyncLock] = {}
        self._meta_lock = asyncio.Lock()

    def get_lock(self, resource_key: str) -> ReentrantAsyncLock:
        """Get or dynamically instantiate a lock for the given resource key."""
        if resource_key not in self._locks:
            self._locks[resource_key] = ReentrantAsyncLock(name=resource_key)
        return self._locks[resource_key]

    @asynccontextmanager
    async def acquire_lock(
        self,
        resource_key: str,
        timeout: float = 5.0,
        owner_token: str | None = None,
    ) -> AsyncIterator[ReentrantAsyncLock]:
        """
        Acquires a granular lock for `resource_key` within `timeout` seconds.
        Usage:
            async with lock_registry.acquire_lock(f"session:{session_id}"):
                # safe critical section
        """
        lock = self.get_lock(resource_key)
        async with lock.hold(timeout=timeout, owner_token=owner_token):
            yield lock

    def remove_lock(self, resource_key: str) -> bool:
        """Clean up an unused lock from the registry if unlocked."""
        lock = self._locks.get(resource_key)
        if lock and not lock.is_locked:
            del self._locks[resource_key]
            return True
        return False

    def active_locks_count(self) -> int:
        return len(self._locks)


# Global singleton registry
default_lock_registry = AsyncLockRegistry()
