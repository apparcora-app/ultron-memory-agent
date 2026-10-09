"""
session_registry.py — Process-Local Session Persistence & Lifecycle Registry.

Manages persistent execution state (sandboxes and browser contexts) keyed by
the composite key f"{bot_id}:{session_id}".

Multi-Process Caveat:
    This registry operates entirely in-memory within the current Python process.
    If Project Ultron is deployed across multiple worker processes (e.g., multiple
    Uvicorn/Gunicorn workers, Celery task workers, or distributed containers),
    sessions are isolated to the specific process handling the request.
    In distributed multi-process environments, sticky session routing (session affinity)
    or an external distributed orchestrator / session store (e.g., Redis or centralized
    daemon) would be required. For single-process or thread-pool deployments, this
    in-memory registry provides complete isolation, session persistence, and TTL cleanup.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ultron.execution.drivers.base_sandbox import BaseSandbox
from ultron.execution.drivers.browser_controller import BrowserController
from ultron.execution.drivers.local_driver import sanitize_identifier
from ultron.execution.drivers.sandbox_factory import get_sandbox

logger = logging.getLogger(__name__)

DEFAULT_SESSION_TTL_SECONDS: int = 1800  # 30 minutes


@dataclass
class SessionEntry:
    """
    State container for an active computer session.

    Holds the isolated sandbox driver, token-compacting browser controller,
    and activity timestamp for TTL eviction.
    """

    bot_id: str
    session_id: str
    sandbox: Optional[BaseSandbox] = None
    browser_controller: Optional[BrowserController] = None
    last_active_at: float = field(default_factory=time.time)

    @property
    def isolation_key(self) -> str:
        """Composite key uniquely identifying this bot/session pair."""
        return f"{self.bot_id}:{self.session_id}"

    @property
    def composite_key(self) -> str:
        """Alias for isolation_key."""
        return self.isolation_key


class SessionRegistry:
    """
    Process-local in-memory registry mapping composite key (bot_id:session_id)
    to active session resources (BaseSandbox and BrowserController).

    Features:
      - Reuses existing sandbox and browser contexts across consecutive actions.
      - Preserves browser authentication, cookies, and DOM state within a session.
      - Configurable TTL eviction for stale / abandoned sessions.
      - Thread-safe registry access using recursive locks.
      - Safe synchronous and asynchronous teardown mechanics.
    """

    def __init__(
        self,
        session_ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS,
        sandbox_base_dir: Optional[str] = None,
        sync_loop_manager: Optional[Any] = None,
    ) -> None:
        self.session_ttl_seconds = max(1, int(session_ttl_seconds))
        self.sandbox_base_dir = sandbox_base_dir
        self._sync_loop_manager = sync_loop_manager
        self._registry: Dict[str, SessionEntry] = {}
        self._lock = threading.RLock()

    def _derive_key(self, bot_id: str, session_id: str) -> str:
        """Sanitize identifiers and generate composite key."""
        clean_bot = sanitize_identifier(bot_id, "bot_id")
        clean_session = sanitize_identifier(session_id, "session_id")
        return f"{clean_bot}:{clean_session}"

    def _close_browser_controller_safely(self, bc: BrowserController) -> None:
        """Close a BrowserController safely handling sync, async, and thread affinities."""
        if bc._browser is None and bc._context is None and bc._playwright is None:
            bc._element_registry.clear()
            return

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            try:
                loop.create_task(bc.close())
            except Exception as exc:
                logger.warning("Error scheduling browser close task: %s", exc)
        else:
            if self._sync_loop_manager is not None:
                try:
                    self._sync_loop_manager.run_coroutine(bc.close())
                    return
                except Exception as exc:
                    logger.warning("Error closing browser controller via sync_loop_manager: %s", exc)

            try:
                asyncio.run(bc.close())
            except Exception as exc:
                logger.warning("Error closing browser controller via asyncio.run: %s", exc)

    async def _close_browser_controller_async(self, bc: BrowserController) -> None:
        """Close a BrowserController asynchronously without thread blocking."""
        if bc._browser is None and bc._context is None and bc._playwright is None:
            bc._element_registry.clear()
            return

        try:
            await bc.close()
        except Exception as exc:
            logger.warning("Error closing browser controller asynchronously: %s", exc)

    def _teardown_entry_sync(self, entry: SessionEntry) -> None:
        """Synchronously release sandbox and browser resources for an entry."""
        if entry.sandbox is not None:
            try:
                entry.sandbox.cleanup()
            except Exception as exc:
                logger.warning("Error cleaning up sandbox for '%s': %s", entry.isolation_key, exc)
            entry.sandbox = None

        if entry.browser_controller is not None:
            bc = entry.browser_controller
            entry.browser_controller = None
            self._close_browser_controller_safely(bc)

    async def _teardown_entry_async(self, entry: SessionEntry) -> None:
        """Asynchronously release sandbox and browser resources for an entry."""
        if entry.sandbox is not None:
            try:
                entry.sandbox.cleanup()
            except Exception as exc:
                logger.warning("Error cleaning up sandbox for '%s': %s", entry.isolation_key, exc)
            entry.sandbox = None

        if entry.browser_controller is not None:
            bc = entry.browser_controller
            entry.browser_controller = None
            await self._close_browser_controller_async(bc)

    def get_or_create_sandbox(self, bot_id: str, session_id: str) -> BaseSandbox:
        """
        Retrieve existing sandbox if within TTL, or instantiate a fresh one.
        Updates last_active_at timestamp.
        """
        clean_bot = sanitize_identifier(bot_id, "bot_id")
        clean_session = sanitize_identifier(session_id, "session_id")
        key = f"{clean_bot}:{clean_session}"
        now = time.time()

        with self._lock:
            if key in self._registry:
                entry = self._registry[key]
                if now - entry.last_active_at > self.session_ttl_seconds:
                    logger.info("Session '%s' expired (TTL=%ds). Evicting old resources.", key, self.session_ttl_seconds)
                    self._teardown_entry_sync(entry)
                    del self._registry[key]
                else:
                    entry.last_active_at = now
                    if entry.sandbox is None:
                        entry.sandbox = get_sandbox(
                            bot_id=clean_bot,
                            session_id=clean_session,
                            base_dir=self.sandbox_base_dir,
                        )
                    return entry.sandbox

            # Provision fresh sandbox and session entry
            sb = get_sandbox(
                bot_id=clean_bot,
                session_id=clean_session,
                base_dir=self.sandbox_base_dir,
            )
            self._registry[key] = SessionEntry(
                bot_id=clean_bot,
                session_id=clean_session,
                sandbox=sb,
                last_active_at=now,
            )
            return sb

    def get_or_create_browser_controller(
        self,
        bot_id: str,
        session_id: str,
        **kwargs: Any,
    ) -> BrowserController:
        """
        Retrieve existing BrowserController if within TTL, or instantiate a fresh one.
        Preserves active browser pages, cookies, and DOM catalog across sequential calls.
        Updates last_active_at timestamp.
        """
        clean_bot = sanitize_identifier(bot_id, "bot_id")
        clean_session = sanitize_identifier(session_id, "session_id")
        key = f"{clean_bot}:{clean_session}"
        now = time.time()

        with self._lock:
            if key in self._registry:
                entry = self._registry[key]
                if now - entry.last_active_at > self.session_ttl_seconds:
                    logger.info("Session '%s' expired (TTL=%ds). Evicting old resources.", key, self.session_ttl_seconds)
                    self._teardown_entry_sync(entry)
                    del self._registry[key]
                else:
                    entry.last_active_at = now
                    if entry.browser_controller is None:
                        entry.browser_controller = BrowserController(
                            bot_id=clean_bot,
                            session_id=clean_session,
                            **kwargs,
                        )
                    return entry.browser_controller

            # Provision fresh browser controller and session entry
            bc = BrowserController(
                bot_id=clean_bot,
                session_id=clean_session,
                **kwargs,
            )
            self._registry[key] = SessionEntry(
                bot_id=clean_bot,
                session_id=clean_session,
                browser_controller=bc,
                last_active_at=now,
            )
            return bc

    def touch(self, bot_id: str, session_id: str) -> None:
        """Update last_active_at timestamp to current time for the given bot and session."""
        try:
            clean_bot = sanitize_identifier(bot_id, "bot_id")
            clean_session = sanitize_identifier(session_id, "session_id")
            key = f"{clean_bot}:{clean_session}"
        except Exception:
            key = f"{bot_id}:{session_id}"
            clean_bot = bot_id
            clean_session = session_id

        now = time.time()
        with self._lock:
            if key in self._registry:
                self._registry[key].last_active_at = now
            else:
                self._registry[key] = SessionEntry(
                    bot_id=clean_bot,
                    session_id=clean_session,
                    last_active_at=now,
                )

    def sweep_expired(self) -> List[str]:
        """
        Scan all active sessions. For any session where (now - last_active_at) > session_ttl_seconds:
          - Calls sandbox.cleanup()
          - Calls browser_controller.close()
          - Removes entry from registry
        Returns list of evicted composite keys.
        """
        now = time.time()
        evicted_keys: List[str] = []
        to_teardown: List[SessionEntry] = []

        with self._lock:
            for key, entry in list(self._registry.items()):
                if now - entry.last_active_at > self.session_ttl_seconds:
                    evicted_keys.append(key)
                    to_teardown.append(entry)
                    del self._registry[key]

        for entry in to_teardown:
            self._teardown_entry_sync(entry)

        if evicted_keys:
            logger.info("SessionRegistry swept and evicted %d expired session(s): %s", len(evicted_keys), evicted_keys)

        return evicted_keys

    async def sweep_expired_async(self) -> List[str]:
        """Asynchronous variant of sweep_expired."""
        now = time.time()
        evicted_keys: List[str] = []
        to_teardown: List[SessionEntry] = []

        with self._lock:
            for key, entry in list(self._registry.items()):
                if now - entry.last_active_at > self.session_ttl_seconds:
                    evicted_keys.append(key)
                    to_teardown.append(entry)
                    del self._registry[key]

        for entry in to_teardown:
            await self._teardown_entry_async(entry)

        if evicted_keys:
            logger.info("SessionRegistry swept and evicted %d expired session(s) asynchronously: %s", len(evicted_keys), evicted_keys)

        return evicted_keys

    def end_session(self, bot_id: str, session_id: str) -> None:
        """
        Explicit teardown. Calls cleanup() on sandbox, close() on browser controller,
        and removes entry from registry. Safe no-op if session does not exist.
        """
        try:
            clean_bot = sanitize_identifier(bot_id, "bot_id")
            clean_session = sanitize_identifier(session_id, "session_id")
            key = f"{clean_bot}:{clean_session}"
        except Exception:
            key = f"{bot_id}:{session_id}"

        entry: Optional[SessionEntry] = None
        with self._lock:
            entry = self._registry.pop(key, None)

        if entry is not None:
            self._teardown_entry_sync(entry)
            logger.info("SessionRegistry ended session '%s'.", key)

    async def end_session_async(self, bot_id: str, session_id: str) -> None:
        """Asynchronous variant of end_session."""
        try:
            clean_bot = sanitize_identifier(bot_id, "bot_id")
            clean_session = sanitize_identifier(session_id, "session_id")
            key = f"{clean_bot}:{clean_session}"
        except Exception:
            key = f"{bot_id}:{session_id}"

        entry: Optional[SessionEntry] = None
        with self._lock:
            entry = self._registry.pop(key, None)

        if entry is not None:
            await self._teardown_entry_async(entry)
            logger.info("SessionRegistry ended session asynchronously '%s'.", key)

    def clear(self) -> None:
        """Synchronously teardown all registered sessions and clear the registry."""
        with self._lock:
            entries = list(self._registry.values())
            self._registry.clear()
        for entry in entries:
            self._teardown_entry_sync(entry)

    async def clear_async(self) -> None:
        """Asynchronously teardown all registered sessions and clear the registry."""
        with self._lock:
            entries = list(self._registry.values())
            self._registry.clear()
        for entry in entries:
            await self._teardown_entry_async(entry)

    def has_session(self, bot_id: str, session_id: str) -> bool:
        """Check if a session exists and is within its TTL."""
        try:
            key = self._derive_key(bot_id, session_id)
        except Exception:
            return False

        now = time.time()
        with self._lock:
            entry = self._registry.get(key)
            if entry is None:
                return False
            if now - entry.last_active_at > self.session_ttl_seconds:
                return False
            return True

    def get_session_entry(self, bot_id: str, session_id: str) -> Optional[SessionEntry]:
        """Retrieve the SessionEntry if active and within TTL, else None."""
        try:
            key = self._derive_key(bot_id, session_id)
        except Exception:
            return None

        now = time.time()
        with self._lock:
            entry = self._registry.get(key)
            if entry is None:
                return None
            if now - entry.last_active_at > self.session_ttl_seconds:
                return None
            return entry

    def get_active_session_count(self) -> int:
        """Return the count of all currently registered sessions."""
        with self._lock:
            return len(self._registry)

    def active_keys(self) -> List[str]:
        """Return a copy of all active composite keys."""
        with self._lock:
            return list(self._registry.keys())
