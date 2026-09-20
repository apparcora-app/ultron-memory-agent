"""
governance/resource_registry.py — Deterministic Resource Lifecycle & Connection Pool Governance.

Provides:
  1. Connection pool boundaries: max_connections, pool_timeout, and starvation prevention.
  2. Strict async context managers guaranteeing leak-free release upon completion, error, or cancellation.
  3. Centralized lifecycle shutdown hook (`shutdown_all()`) closing all pools and connections.
  4. Active lease tracking and leak detection (verifying 0 lingering sockets/sessions).
"""

from __future__ import annotations

import asyncio
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Callable, Coroutine, Dict, List, Optional, Set


class PoolStarvationError(TimeoutError):
    """Raised when acquiring a resource from a pool exceeds pool_timeout due to exhaustion."""

    def __init__(self, pool_name: str, max_connections: int, timeout_sec: float) -> None:
        super().__init__(
            f"Resource pool '{pool_name}' starved: all {max_connections} connections in use. "
            f"Failed to acquire connection within {timeout_sec:.2f}s timeout."
        )
        self.pool_name = pool_name
        self.max_connections = max_connections
        self.timeout_sec = timeout_sec


class ManagedResource:
    """Represents a single checked-out connection or session handle."""

    def __init__(self, resource_id: str, pool_name: str, raw_object: Any) -> None:
        self.resource_id = resource_id
        self.pool_name = pool_name
        self.raw_object = raw_object
        self.acquired_at = time.time()
        self.is_active = True

    def mark_closed(self) -> None:
        self.is_active = False


class ResourcePool:
    """
    Bounded connection pool with deterministic async lifecycle tracking.
    Guarantees cleanup even under asyncio.CancelledError or exceptions.
    """

    def __init__(
        self,
        name: str,
        max_connections: int = 10,
        pool_timeout_sec: float = 5.0,
        factory: Optional[Callable[[], Any]] = None,
        closer: Optional[Callable[[Any], Any]] = None,
    ) -> None:
        self.name = name
        self.max_connections = max_connections
        self.pool_timeout_sec = pool_timeout_sec
        self.factory = factory or (lambda: {"id": uuid.uuid4().hex[:8], "status": "connected"})
        self.closer = closer or (lambda obj: None)

        self._semaphore = asyncio.Semaphore(max_connections)
        self._active_leases: Dict[str, ManagedResource] = {}
        self._lock = asyncio.Lock()
        self._is_shutdown = False

    @property
    def active_count(self) -> int:
        return len(self._active_leases)

    @property
    def available_slots(self) -> int:
        return self.max_connections - len(self._active_leases)

    @asynccontextmanager
    async def acquire(self, timeout: Optional[float] = None) -> AsyncIterator[ManagedResource]:
        """
        Leases a connection from the pool.
        Guarantees release back to pool even if task is cancelled.
        """
        if self._is_shutdown:
            raise RuntimeError(f"Cannot acquire from pool '{self.name}': pool is shut down.")

        timeout_sec = timeout if timeout is not None else self.pool_timeout_sec
        acquired_sem = False

        try:
            # Wait for available connection slot
            try:
                await asyncio.wait_for(self._semaphore.acquire(), timeout=timeout_sec)
                acquired_sem = True
            except asyncio.TimeoutError as err:
                raise PoolStarvationError(self.name, self.max_connections, timeout_sec) from err

            # Instantiate / checkout managed resource
            res_id = f"{self.name}_{uuid.uuid4().hex[:8]}"
            raw = self.factory()
            if asyncio.iscoroutine(raw):
                raw = await raw

            resource = ManagedResource(resource_id=res_id, pool_name=self.name, raw_object=raw)
            async with self._lock:
                self._active_leases[res_id] = resource

            try:
                yield resource
            finally:
                # Guaranteed cleanup: close raw object and release lease
                async with self._lock:
                    if res_id in self._active_leases:
                        leased = self._active_leases.pop(res_id)
                        leased.mark_closed()

                try:
                    close_res = self.closer(raw)
                    if asyncio.iscoroutine(close_res):
                        await close_res
                except Exception:
                    pass  # suppress error during closer to ensure semaphore release

        finally:
            if acquired_sem:
                self._semaphore.release()

    async def close_all(self) -> None:
        """Force-closes all active resources and shuts down the pool."""
        self._is_shutdown = True
        async with self._lock:
            for res_id, res in list(self._active_leases.items()):
                try:
                    close_res = self.closer(res.raw_object)
                    if asyncio.iscoroutine(close_res):
                        await close_res
                except Exception:
                    pass
                res.mark_closed()
            self._active_leases.clear()


class ResourceRegistry:
    """
    Central governance registry for all connection pools, database clients,
    and HTTP/MCP sessions.
    """

    def __init__(self) -> None:
        self._pools: Dict[str, ResourcePool] = {}
        self._cleanup_hooks: List[Callable[[], Any]] = []
        self._lock = asyncio.Lock()

    def register_pool(
        self,
        name: str,
        max_connections: int = 10,
        pool_timeout_sec: float = 5.0,
        factory: Optional[Callable[[], Any]] = None,
        closer: Optional[Callable[[Any], Any]] = None,
    ) -> ResourcePool:
        pool = ResourcePool(
            name=name,
            max_connections=max_connections,
            pool_timeout_sec=pool_timeout_sec,
            factory=factory,
            closer=closer,
        )
        self._pools[name] = pool
        return pool

    def get_pool(self, name: str) -> ResourcePool:
        if name not in self._pools:
            self.register_pool(name)
        return self._pools[name]

    @asynccontextmanager
    async def lease(
        self,
        pool_name: str,
        timeout: Optional[float] = None,
    ) -> AsyncIterator[ManagedResource]:
        """Convenience context manager to lease from a named pool."""
        pool = self.get_pool(pool_name)
        async with pool.acquire(timeout=timeout) as res:
            yield res

    def register_cleanup_hook(self, hook: Callable[[], Any]) -> None:
        """Registers a global shutdown / cleanup coroutine or function."""
        self._cleanup_hooks.append(hook)

    async def shutdown_all(self) -> None:
        """Cleanly drains and shuts down all active pools and executes cleanup hooks."""
        for pool in list(self._pools.values()):
            await pool.close_all()
        self._pools.clear()

        for hook in self._cleanup_hooks:
            try:
                res = hook()
                if asyncio.iscoroutine(res):
                    await res
            except Exception:
                pass
        self._cleanup_hooks.clear()

    def active_leak_count(self, pool_name: Optional[str] = None) -> int:
        """Returns total active resource checkouts across all pools (or a single pool)."""
        if pool_name:
            pool = self._pools.get(pool_name)
            return pool.active_count if pool else 0
        return sum(pool.active_count for pool in self._pools.values())


# Global default registry instance
default_resource_registry = ResourceRegistry()
