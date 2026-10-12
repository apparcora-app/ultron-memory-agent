"""
handoff_manager.py — Take-the-Wheel State Machine for Human In-The-Loop Execution.

Detects bot challenges (CAPTCHA, Cloudflare, 2FA/MFA) in browser perception snapshots
and halts autonomous execution to hand control over to a human operator until wheel release.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from ultron.execution.computer_contracts import BrowserSnapshot

logger = logging.getLogger(__name__)

# Patterns signaling CAPTCHA, bot detection, Cloudflare, or 2FA
CHALLENGE_PATTERNS = (
    # CAPTCHA variants
    (re.compile(r"\b(recaptcha|hcaptcha|turnstile|geetest|arkoselabs|funcaptcha)\b", re.IGNORECASE), "CAPTCHA Challenge"),
    (re.compile(r"verify\s+you\s+are\s+human", re.IGNORECASE), "Human Verification Prompt"),
    (re.compile(r"i['’]?m\s+not\s+a\s+robot", re.IGNORECASE), "reCAPTCHA Checkbox"),
    (re.compile(r"bot\s+detection", re.IGNORECASE), "Bot Detection Challenge"),
    # Cloudflare waiting rooms and anti-bot verification
    (re.compile(r"checking\s+your\s+browser", re.IGNORECASE), "Cloudflare Browser Verification"),
    (re.compile(r"just\s+a\s+moment\.\.\.", re.IGNORECASE), "Cloudflare Interstitial Screen"),
    (re.compile(r"attention\s+required!\s*\|\s*cloudflare", re.IGNORECASE), "Cloudflare Access Block"),
    (re.compile(r"\bray\s+id:\s*[0-9a-f]+", re.IGNORECASE), "Cloudflare Ray ID Wall"),
    # Two-Factor / Multi-Factor Authentication
    (re.compile(r"\b(two-factor|multi-factor|2fa|mfa)\b", re.IGNORECASE), "Multi-Factor Authentication (2FA/MFA)"),
    (re.compile(r"one-time\s+password", re.IGNORECASE), "OTP Challenge"),
    (re.compile(r"enter\s+(the\s+)?verification\s+code", re.IGNORECASE), "Verification Code Prompt"),
    (re.compile(r"authenticator\s+app", re.IGNORECASE), "Authenticator App Prompt"),
)


class HandoffManager:
    """
    Manages the OpenBot Take-the-Wheel state machine.

    Enforces:
      - Automatic detection of CAPTCHA, Cloudflare, and 2FA challenges.
      - Immediate execution lockdown while takeover is active.
      - Structured handoff event generation containing URL, screenshot, and reason.
      - Explicit wheel release mechanism to restore autonomous execution.
    """

    def __init__(self) -> None:
        # Tracks active takeover state per session: session_id -> bool
        self.session_takeover_active: dict[str, bool] = {}
        # Stores active handoff event metadata: session_id -> dict
        self._active_handoff_events: dict[str, dict[str, Any]] = {}

    def detect_takeover_need(self, snapshot: BrowserSnapshot) -> tuple[bool, str | None]:
        """
        Inspect a BrowserSnapshot for CAPTCHA, Cloudflare, or 2FA indicators.

        Returns:
            Tuple[bool, Optional[str]]: (needs_takeover, detected_reason)
        """
        content_sources = [
            snapshot.title,
            snapshot.url,
            snapshot.aria_tree,
        ]
        # Include interactive element texts
        for elem in snapshot.interactive_elements:
            elem_text = elem.get("text", "")
            if elem_text:
                content_sources.append(elem_text)

        combined_text = "\n".join(content_sources)

        for pattern, label in CHALLENGE_PATTERNS:
            if pattern.search(combined_text):
                return True, f"Automated execution paused: {label} detected."

        return False, None

    def trigger_takeover(
        self,
        session_id: str,
        snapshot: BrowserSnapshot,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """
        Engage the Take-the-Wheel state for a session and generate a handoff event.

        Args:
            session_id: The active session ID.
            snapshot: Current BrowserSnapshot containing URL, title, and screenshot.
            reason: Optional description of why takeover was triggered.

        Returns:
            Dict[str, Any]: Structured handoff event payload.
        """
        effective_reason = reason or "Operator intervention required for verification challenge."
        self.session_takeover_active[session_id] = True

        handoff_event = {
            "session_id": session_id,
            "status": "TAKEOVER_IN_PROGRESS",
            "url": snapshot.url,
            "title": snapshot.title,
            "screenshot_b64": snapshot.screenshot_b64,
            "reason": effective_reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self._active_handoff_events[session_id] = handoff_event
        logger.warning(
            "Take-the-Wheel engaged for session '%s'. Reason: %s",
            session_id,
            effective_reason,
        )
        return handoff_event

    def is_takeover_active(self, session_id: str) -> bool:
        """
        Check if manual takeover is currently active for a session.
        While active, any automated action attempts must be immediately rejected
        with status 'TAKEOVER_IN_PROGRESS'.
        """
        return self.session_takeover_active.get(session_id, False)

    def check_execution_permitted(self, session_id: str) -> tuple[bool, str]:
        """
        Gate check for execution engines. Rejects with 'TAKEOVER_IN_PROGRESS'
        if human intervention is currently active.
        """
        if self.is_takeover_active(session_id):
            return False, "TAKEOVER_IN_PROGRESS"
        return True, "PERMITTED"

    def release_wheel(self, session_id: str, success: bool = True) -> None:
        """
        Resume autonomous execution loop after operator completes manual intervention.

        Args:
            session_id: The active session ID.
            success: Whether the operator successfully resolved the challenge.
        """
        self.session_takeover_active[session_id] = False
        self._active_handoff_events.pop(session_id, None)
        logger.info(
            "Wheel released for session '%s' (success=%s). Autonomous execution resumed.",
            session_id,
            success,
        )

    def get_active_event(self, session_id: str) -> dict[str, Any] | None:
        """Retrieve the active handoff event payload for a session."""
        return self._active_handoff_events.get(session_id)
