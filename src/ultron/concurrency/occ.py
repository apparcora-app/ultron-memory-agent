"""
concurrency/occ.py — State Versioning & Optimistic Concurrency Control (OCC).

Provides:
  1. StateConcurrencyConflictError: Structured exception raised on version mismatch.
  2. OCCStateManager: Memory & state container enforcing monotonic integer versions (`version: int`).
  3. Atomic conditional mutation logic asserting `expected_version == current_version`.
  4. Safe automated rebase and retry mechanism (`atomic_mutate`).
"""

from __future__ import annotations

import asyncio
import copy
import random
from collections.abc import Callable
from typing import Any


class StateConcurrencyConflictError(RuntimeError):
    """Raised when an update is attempted against a stale state version."""

    def __init__(
        self,
        resource_id: str,
        expected_version: int,
        actual_version: int,
        message: str | None = None,
    ) -> None:
        msg = message or (
            f"Concurrency conflict on resource '{resource_id}': "
            f"expected version {expected_version}, but actual version is {actual_version}. "
            f"Another coroutine committed an update first."
        )
        super().__init__(msg)
        self.resource_id = resource_id
        self.expected_version = expected_version
        self.actual_version = actual_version

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": "StateConcurrencyConflictError",
            "resource_id": self.resource_id,
            "expected_version": self.expected_version,
            "actual_version": self.actual_version,
        }


class OCCStateManager:
    """
    Optimistic Concurrency Control manager for state dictionaries.
    Maintains monotonic integer versions (`version: int`) and verifies atomic transitions.
    """

    def __init__(self) -> None:
        self._states: dict[str, dict[str, Any]] = {}
        self._versions: dict[str, int] = {}
        self._lock = asyncio.Lock()

    async def get_state(self, resource_id: str, default: dict[str, Any] | None = None) -> tuple[dict[str, Any], int]:
        """
        Returns a deep copy of the current state and its integer version.
        Initializes state at version 1 if not present.
        """
        async with self._lock:
            if resource_id not in self._states:
                initial = copy.deepcopy(default or {})
                initial["version"] = 1
                self._states[resource_id] = initial
                self._versions[resource_id] = 1

            version = self._versions[resource_id]
            return copy.deepcopy(self._states[resource_id]), version

    async def commit_update(
        self,
        resource_id: str,
        updated_state: dict[str, Any],
        expected_version: int,
    ) -> int:
        """
        Atomically commits an updated state if expected_version matches current version.
        Increments the state version on success.
        Raises StateConcurrencyConflictError on collision.
        """
        async with self._lock:
            current_version = self._versions.get(resource_id, 1)

            if expected_version != current_version:
                raise StateConcurrencyConflictError(
                    resource_id=resource_id,
                    expected_version=expected_version,
                    actual_version=current_version,
                )

            next_version = current_version + 1
            state_to_store = copy.deepcopy(updated_state)
            state_to_store["version"] = next_version

            self._states[resource_id] = state_to_store
            self._versions[resource_id] = next_version
            return next_version

    async def atomic_mutate(
        self,
        resource_id: str,
        mutator_fn: Callable[[dict[str, Any]], dict[str, Any]],
        max_retries: int = 10,
        backoff_base_sec: float = 0.005,
    ) -> tuple[dict[str, Any], int]:
        """
        Rebase-and-retry helper:
          1. Fetches current state & version.
          2. Applies user-provided `mutator_fn`.
          3. Attempts `commit_update`.
          4. If a conflict occurs, backs off briefly and re-fetches latest state.
        """
        for attempt in range(1, max_retries + 1):
            current_state, current_version = await self.get_state(resource_id)
            transformed = mutator_fn(copy.deepcopy(current_state))

            try:
                new_version = await self.commit_update(
                    resource_id=resource_id,
                    updated_state=transformed,
                    expected_version=current_version,
                )
                transformed["version"] = new_version
                return transformed, new_version
            except StateConcurrencyConflictError as conflict:
                if attempt == max_retries:
                    raise StateConcurrencyConflictError(
                        resource_id=resource_id,
                        expected_version=conflict.expected_version,
                        actual_version=conflict.actual_version,
                        message=f"Exceeded max retries ({max_retries}) for atomic mutation on '{resource_id}'.",
                    ) from conflict

                # Exponential backoff with random jitter to prevent thundering herd
                jitter = random.uniform(0.5, 1.5)
                delay = (backoff_base_sec * (2 ** (attempt - 1))) * jitter
                await asyncio.sleep(delay)

        raise RuntimeError("Unexpected exit from atomic_mutate loop.")


# Default global state manager
default_occ_manager = OCCStateManager()
