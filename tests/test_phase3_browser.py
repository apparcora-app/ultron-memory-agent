"""
test_phase3_browser.py — Verification Test Suite for OpenBot Phase 3: Browser Engine & Take-the-Wheel Handoff.

Tests:
  1. ARIA snapshot token compaction: produces lightweight numbered ARIA string well under 1,500 tokens instead of raw HTML.
  2. Element interaction: clicking and typing via 1-based catalog IDs.
  3. Catalog truncation at 40 elements with [...remaining elements omitted].
  4. Take-the-Wheel detection for CAPTCHA, Cloudflare, and 2FA challenges.
  5. Action blocking with 'TAKEOVER_IN_PROGRESS' while takeover is active.
  6. Wheel release resuming normal execution flow.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure ultron-memory-agent root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ultron.execution.computer_contracts import BrowserSnapshot
from ultron.execution.drivers.browser_controller import BrowserController, MAX_ARIA_CATALOG_ELEMENTS
from ultron.execution.takeover.handoff_manager import HandoffManager


# ── Test 1: ARIA Token Compaction & Token Budget ──────────────────────────────

@pytest.mark.asyncio
async def test_snapshot_token_compaction_under_1500_tokens():
    """
    Verify that snapshot output produces a formatted ARIA string under 1,500 tokens
    instead of raw HTML.
    """
    async with BrowserController(headless=True) as controller:
        # Load a representative web document with multiple forms, links, and buttons
        html_content = """
        <!DOCTYPE html>
        <html>
        <head><title>Ultron Portal - Mission Control</title></head>
        <body>
            <header>
                <h1>Mission Control</h1>
                <nav>
                    <a href="/dashboard">Dashboard</a>
                    <a href="/docs">Documentation</a>
                    <a href="/settings">Settings</a>
                </nav>
            </header>
            <main>
                <section>
                    <form id="search-form">
                        <label for="q">Query:</label>
                        <input type="text" id="q" placeholder="Enter command query..." aria-label="Query Input" />
                        <button type="submit">Execute Query</button>
                    </form>
                </section>
                <section>
                    <h2>Action Panel</h2>
                    <button id="btn-sync">Synchronize Ledger</button>
                    <button id="btn-export">Export Financials</button>
                    <textarea placeholder="Operator notes..."></textarea>
                </section>
            </main>
        </body>
        </html>
        """
        await controller.page.set_content(html_content)
        snapshot = await controller.get_current_snapshot()

        assert snapshot.title == "Ultron Portal - Mission Control"
        assert not snapshot.aria_tree.startswith("<!DOCTYPE")
        assert not snapshot.aria_tree.startswith("<html")

        # Verify formatted numbered catalog
        lines = [line for line in snapshot.aria_tree.split("\n") if line.strip()]
        assert len(lines) >= 5

        # Check line format: [1] Link: "Dashboard", etc.
        assert any('[1] Link: "Dashboard"' in line for line in lines)
        assert any('Button: "Execute Query"' in line for line in lines)
        assert any('Input (text): "Query Input"' in line or 'Input (text): "Enter command query..."' in line for line in lines)

        # Estimate tokens (~4 characters per token heuristic)
        estimated_tokens = len(snapshot.aria_tree) / 4.0
        assert estimated_tokens < 1500, f"ARIA tree exceeded token cap: {estimated_tokens} tokens"
        assert estimated_tokens < 300  # Highly compact, typically under 150 tokens


# ── Test 2: Element Interaction via Catalog IDs ───────────────────────────────

@pytest.mark.asyncio
async def test_click_and_type_via_catalog_ids():
    """
    Verify clicking and typing into interactive elements using their assigned catalog IDs.
    """
    async with BrowserController(headless=True) as controller:
        html = """
        <html>
        <head><title>Form Interaction Test</title></head>
        <body>
            <input type="text" id="target-input" placeholder="Type here" aria-label="Username" />
            <button id="action-btn" onclick="document.title='Button Clicked!'">Submit Form</button>
        </body>
        </html>
        """
        await controller.page.set_content(html)
        snapshot = await controller.get_current_snapshot()

        # Find element IDs
        input_id = None
        button_id = None
        for elem in snapshot.interactive_elements:
            if "Username" in elem["text"] or "Type here" in elem["text"]:
                input_id = elem["id"]
            if "Submit Form" in elem["text"]:
                button_id = elem["id"]

        assert input_id is not None
        assert button_id is not None

        # 1. Type into input
        snapshot_after_type = await controller.type_text(input_id, "UltronPrimeAgent")
        val = await controller.page.locator("#target-input").input_value()
        assert val == "UltronPrimeAgent"

        # 2. Click button
        snapshot_after_click = await controller.click_element(button_id)
        assert snapshot_after_click.title == "Button Clicked!"


# ── Test 3: Catalog Truncation at 40 Elements ─────────────────────────────────

@pytest.mark.asyncio
async def test_aria_catalog_truncation_at_40_elements():
    """
    Verify that pages with more than 40 interactive elements are cleanly truncated
    at 40 items with [...remaining elements omitted] appended.
    """
    async with BrowserController(headless=True) as controller:
        # Generate 60 interactive buttons
        buttons_html = "\n".join(f'<button id="btn-{i}">Action Item {i}</button>' for i in range(1, 61))
        html = f"<html><body><h1>High Density Page</h1>{buttons_html}</body></html>"

        await controller.page.set_content(html)
        snapshot = await controller.get_current_snapshot()

        assert len(snapshot.interactive_elements) == 40
        assert "[...remaining elements omitted]" in snapshot.aria_tree
        assert '[40] Button: "Action Item 40"' in snapshot.aria_tree
        assert '[41] Button:' not in snapshot.aria_tree


# ── Test 4: Takeover Challenge Detection ──────────────────────────────────────

def test_takeover_detection_captcha():
    """
    Verify that CAPTCHA keywords in snapshot trigger takeover recommendation.
    """
    manager = HandoffManager()
    snapshot = BrowserSnapshot(
        url="https://protected.target.com/login",
        title="Security Check - Solve the CAPTCHA",
        aria_tree='[1] Button: "Verify you are human"\n[2] Link: "Privacy"',
        interactive_elements=[{"id": 1, "text": "Verify you are human"}],
        screenshot_b64="dGVzdF9pbWFnZQ==",
    )

    needs_takeover, reason = manager.detect_takeover_need(snapshot)
    assert needs_takeover is True
    assert reason is not None
    assert "CAPTCHA" in reason or "Human Verification" in reason


def test_takeover_detection_cloudflare():
    """
    Verify that Cloudflare interstitial screen triggers takeover.
    """
    manager = HandoffManager()
    snapshot = BrowserSnapshot(
        url="https://cloudflare-protected.com/",
        title="Just a moment...",
        aria_tree='[1] Element: "Checking your browser before accessing..."',
        interactive_elements=[],
        screenshot_b64=None,
    )

    needs_takeover, reason = manager.detect_takeover_need(snapshot)
    assert needs_takeover is True
    assert "Cloudflare" in reason


def test_takeover_detection_2fa():
    """
    Verify that 2FA/MFA challenge screens trigger takeover.
    """
    manager = HandoffManager()
    snapshot = BrowserSnapshot(
        url="https://banking.portal.com/auth/mfa",
        title="Two-Factor Authentication",
        aria_tree='[1] Input (text): "Enter verification code"\n[2] Button: "Verify OTP"',
        interactive_elements=[{"id": 1, "text": "Enter verification code"}],
        screenshot_b64=None,
    )

    needs_takeover, reason = manager.detect_takeover_need(snapshot)
    assert needs_takeover is True
    assert "2FA" in reason or "Multi-Factor" in reason or "Verification Code" in reason


def test_takeover_clean_page_no_detection():
    """
    Verify that normal web pages do not trigger false-positive takeovers.
    """
    manager = HandoffManager()
    snapshot = BrowserSnapshot(
        url="https://news.ycombinator.com/",
        title="Hacker News",
        aria_tree='[1] Link: "Hacker News"\n[2] Link: "new"\n[3] Link: "comments"',
        interactive_elements=[],
        screenshot_b64=None,
    )

    needs_takeover, reason = manager.detect_takeover_need(snapshot)
    assert needs_takeover is False
    assert reason is None


# ── Test 5: Takeover Action Blocking & Wheel Release ──────────────────────────

def test_takeover_blocks_execution_until_wheel_release():
    """
    Verify takeover state blocks automated action attempts with status 'TAKEOVER_IN_PROGRESS',
    and unblocks when release_wheel() is called.
    """
    manager = HandoffManager()
    session_id = "session_takeover_999"

    snapshot = BrowserSnapshot(
        url="https://vendor.portal.com/auth",
        title="Attention Required! | Cloudflare",
        aria_tree='[1] Element: "Ray ID: 7abcdef123456"',
        interactive_elements=[],
        screenshot_b64="base64_screenshot_data",
    )

    # 1. Initially, execution is permitted
    can_exec, status = manager.check_execution_permitted(session_id)
    assert can_exec is True
    assert status == "PERMITTED"

    # 2. Engage takeover
    event = manager.trigger_takeover(session_id, snapshot, reason="Cloudflare Ray ID wall detected.")
    assert manager.is_takeover_active(session_id) is True
    assert event["status"] == "TAKEOVER_IN_PROGRESS"
    assert event["url"] == snapshot.url
    assert event["screenshot_b64"] == "base64_screenshot_data"

    # 3. Action attempt while active MUST be rejected with 'TAKEOVER_IN_PROGRESS'
    can_exec_blocked, blocked_status = manager.check_execution_permitted(session_id)
    assert can_exec_blocked is False
    assert blocked_status == "TAKEOVER_IN_PROGRESS"

    # 4. Release the wheel
    manager.release_wheel(session_id, success=True)
    assert manager.is_takeover_active(session_id) is False

    # 5. Normal execution loop resumed
    can_exec_resumed, resumed_status = manager.check_execution_permitted(session_id)
    assert can_exec_resumed is True
    assert resumed_status == "PERMITTED"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
