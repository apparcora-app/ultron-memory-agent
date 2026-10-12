"""
evidence_ledger.py — Per-turn immutable evidence store (v2).

Additions vs v1
---------------
* ScopeEntry  — records actual row/item counts from real data loads
* record_scope() — second write path, callable ONLY from scope_integrity.py
                   (the module that performs the real len() call)
* all_scope_entries — read-only snapshot for the gate and debuggers

All v1 invariants preserved:
* record() still called only from tool_executor.py
* record_scope() called only from scope_integrity.py
* Both are append-only; entries are immutable once written
* get() unchanged
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime

# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LedgerEntry:
    """Immutable snapshot of one real tool execution result."""
    tool_name:    str
    tool_call_id: str
    raw_stdout:   str
    raw_stderr:   str
    exit_code:    int
    timestamp:    datetime


@dataclass(frozen=True)
class ScopeEntry:
    """
    Immutable snapshot of a real dataset load.

    Fields
    ------
    scope_id        : stable ID for this load event
    source_path     : file or identifier that was loaded
    actual_count    : len() of the real loaded object — never a claimed number
    item_label      : human label for what is being counted ('rows', 'items', …)
    timestamp       : UTC timestamp of the load
    """
    scope_id:    str
    source_path: str
    actual_count: int
    item_label:  str
    timestamp:   datetime


class DuplicateEntryError(Exception):
    """Raised when code attempts to overwrite an existing ledger entry."""


# ---------------------------------------------------------------------------
# EvidenceLedger
# ---------------------------------------------------------------------------

class EvidenceLedger:
    """
    Append-only store for tool-execution evidence and scope counts.

    Thread-safe.

    Write paths (each has exactly ONE authorised call-site)
    -------------------------------------------------------
    record(...)       — tool_executor.py only
    record_scope(...) — scope_integrity.py only

    Read paths (available to gate and debuggers)
    --------------------------------------------
    get(tool_call_id)     -> LedgerEntry | None
    get_scope(scope_id)   -> ScopeEntry  | None
    all_entries           -> dict snapshot of tool entries
    all_scope_entries     -> dict snapshot of scope entries
    """

    def __init__(self, turn_id: str) -> None:
        self._turn_id = turn_id
        self._entries: dict[str, LedgerEntry] = {}
        self._scope_entries: dict[str, ScopeEntry] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Write path 1 — called ONLY from tool_executor.py
    # ------------------------------------------------------------------

    def record(
        self,
        tool_name:    str,
        tool_call_id: str,
        raw_stdout:   str,
        raw_stderr:   str,
        exit_code:    int,
        timestamp:    datetime,
    ) -> LedgerEntry:
        """Record a real tool-execution result. Immutable once written."""
        if not tool_call_id or not isinstance(tool_call_id, str):
            raise ValueError(
                f"tool_call_id must be a non-empty string, got {tool_call_id!r}"
            )

        entry = LedgerEntry(
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            raw_stdout=raw_stdout,
            raw_stderr=raw_stderr,
            exit_code=exit_code,
            timestamp=timestamp,
        )

        with self._lock:
            if tool_call_id in self._entries:
                raise DuplicateEntryError(
                    f"Entry {tool_call_id!r} already recorded — ledger is immutable."
                )
            self._entries[tool_call_id] = entry

        return entry

    # ------------------------------------------------------------------
    # Write path 2 — called ONLY from scope_integrity.py
    # ------------------------------------------------------------------

    def record_scope(
        self,
        scope_id:     str,
        source_path:  str,
        actual_count: int,
        item_label:   str,
        timestamp:    datetime,
    ) -> ScopeEntry:
        """
        Record a real dataset row/item count.

        actual_count must be the result of len() on the real loaded object —
        never a claimed or estimated number.
        Raises DuplicateEntryError if scope_id already exists.
        """
        if not scope_id or not isinstance(scope_id, str):
            raise ValueError(
                f"scope_id must be a non-empty string, got {scope_id!r}"
            )
        if not isinstance(actual_count, int) or actual_count < 0:
            raise ValueError(
                f"actual_count must be a non-negative int, got {actual_count!r}"
            )

        entry = ScopeEntry(
            scope_id=scope_id,
            source_path=source_path,
            actual_count=actual_count,
            item_label=item_label,
            timestamp=timestamp,
        )

        with self._lock:
            if scope_id in self._scope_entries:
                raise DuplicateEntryError(
                    f"Scope entry {scope_id!r} already recorded — ledger is immutable."
                )
            self._scope_entries[scope_id] = entry

        return entry

    # ------------------------------------------------------------------
    # Read paths
    # ------------------------------------------------------------------

    def get(self, tool_call_id: str) -> LedgerEntry | None:
        """Return the LedgerEntry for this call ID, or None."""
        with self._lock:
            return self._entries.get(tool_call_id)

    def get_scope(self, scope_id: str) -> ScopeEntry | None:
        """Return the ScopeEntry for this scope ID, or None."""
        with self._lock:
            return self._scope_entries.get(scope_id)

    @property
    def all_entries(self) -> dict[str, LedgerEntry]:
        """Shallow copy of all tool-execution entries."""
        with self._lock:
            return dict(self._entries)

    @property
    def all_scope_entries(self) -> dict[str, ScopeEntry]:
        """Shallow copy of all scope entries."""
        with self._lock:
            return dict(self._scope_entries)

    @property
    def turn_id(self) -> str:
        return self._turn_id

    def __repr__(self) -> str:
        n = len(self._entries)
        s = len(self._scope_entries)
        return (
            f"<EvidenceLedger turn_id={self._turn_id!r} "
            f"tool_entries={n} scope_entries={s}>"
        )
