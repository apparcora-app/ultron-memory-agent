"""
sandbox_factory.py — Sandbox Factory for Dynamic Driver Selection & Resilient Fallback.

Checks for E2B credentials and cloud dependencies. If available, provisions an E2B
Firecracker microVM driver; otherwise safely logs fallback and returns a hardened LocalDriver.
Scopes sandbox instances by composite (bot_id:session_id) isolation key.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from ultron.execution.drivers.base_sandbox import BaseSandbox
from ultron.execution.drivers.local_driver import LocalDriver

logger = logging.getLogger(__name__)


def get_sandbox(
    bot_id: Optional[str] = None,
    session_id: Optional[str] = None,
    api_key: Optional[str] = None,
    base_dir: Optional[str] = None,
    **kwargs: Any,
) -> BaseSandbox:
    """
    Factory function to instantiate an isolated sandbox environment scoped per (bot_id, session_id).

    Logic:
      1. Derives isolation key as f"{bot_id}:{session_id}".
      2. Checks for 'E2B_API_KEY' in args or os.environ.
      3. If present, attempts to instantiate E2BDriver tagged with composite key.
      4. If missing, or if E2B dependencies/network fail, logs fallback and returns LocalDriver
         with workspace folder ./data/workspace/sandbox_<bot_id>_<session_id>/.

    Args:
        bot_id: Unique bot/agent identifier.
        session_id: Unique session identifier for workspace scoping.
        api_key: Optional explicit E2B API key.
        base_dir: Optional base directory override for LocalDriver.

    Returns:
        BaseSandbox: An active sandbox instance (E2BDriver or LocalDriver).
    """
    raw_bot_id = kwargs.get("bot_id", bot_id)
    raw_session_id = kwargs.get("session_id", session_id)

    # Disambiguate single positional argument for backward-compatibility
    if raw_bot_id is not None and raw_session_id is None and "session_id" not in kwargs:
        eff_bot_id = "default_bot"
        eff_session_id = raw_bot_id
    else:
        eff_bot_id = "default_bot" if raw_bot_id is None else raw_bot_id
        eff_session_id = "default" if raw_session_id is None else raw_session_id

    isolation_key = f"{eff_bot_id}:{eff_session_id}"
    effective_api_key = api_key or os.getenv("E2B_API_KEY")

    if effective_api_key:
        try:
            from ultron.execution.drivers.e2b_driver import E2BDriver

            logger.info(
                "E2B_API_KEY detected. Provisioning cloud microVM sandbox for key '%s'...",
                isolation_key,
            )
            return E2BDriver(
                bot_id=eff_bot_id,
                session_id=eff_session_id,
                api_key=effective_api_key,
            )
        except ImportError as exc:
            logger.warning(
                "E2B_API_KEY was provided, but E2B SDK is not installed (%s). "
                "Safely falling back to LocalDriver.",
                exc,
            )
        except Exception as exc:
            logger.warning(
                "Failed to initialize E2BDriver (%s). Safely falling back to LocalDriver.",
                exc,
            )

    # Local fallback path
    logger.info(
        "No E2B credentials configured or E2B unavailable. Engaging LocalDriver for key '%s'.",
        isolation_key,
    )
    if base_dir:
        return LocalDriver(
            bot_id=eff_bot_id,
            session_id=eff_session_id,
            base_dir=base_dir,
        )
    return LocalDriver(
        bot_id=eff_bot_id,
        session_id=eff_session_id,
    )
