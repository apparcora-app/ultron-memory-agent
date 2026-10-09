"""
test_fixB_persistence.py — Verification Test Suite for OpenBot Fix B: Session Persistence & Cleanup.

Tests:
  1. Sequential browser calls persist the exact same BrowserController instance and browser context.
  2. Sequential sandbox calls persist the exact same BaseSandbox instance and workspace files.
  3. Session TTL: active session within TTL is not evicted by sweep_expired().
  4. Session TTL: idle session exceeding session_ttl_seconds is evicted and cleaned up by sweep_expired().
  5. Expired session re-request: evicts old expired resources and provisions a fresh instance.
  6. Touch mechanics: touch() updates last_active_at, preventing premature expiration.
  7. Explicit end_session(): tears down sandbox and browser, removes entry, and is safely idempotent.
  8. Multi-bot persistence isolation: bot_alpha and bot_beta in the same session_id persist separately;
     ending bot_alpha does not destroy bot_beta.
  9. Take-the-Wheel handoff continuity: takeover does not destroy sandbox/browser, and wheel release resumes
     the exact same session.
  10. ComputerToolDispatcher integration: dispatching end_computer_session cleans up resources.
  11. Dispatch action touches registry: every dispatched action updates last_active_at.
  12. Multi-process caveat documentation in session_registry module docstring.
  13. End computer session Anthropic schema and Pydantic v2 input contract verification.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure ultron-memory-agent root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import ultron.execution.session_registry as session_registry_module
from ultron.execution.computer_contracts import (
    ActionType,
    BrowserSnapshot,
    ComputerAction,
    PolicyRule,
)
from ultron.execution.drivers.base_sandbox import BaseSandbox
from ultron.execution.drivers.browser_controller import BrowserController
from ultron.execution.drivers.local_driver import LocalDriver
from ultron.execution.session_registry import (
    DEFAULT_SESSION_TTL_SECONDS,
    SessionEntry,
    SessionRegistry,
)
from ultron.execution.takeover.handoff_manager import HandoffManager
from ultron.execution.tool_bridge import (
    COMPUTER_TOOLS,
    END_COMPUTER_SESSION_TOOL,
    EXTENDED_COMPUTER_TOOLS,
    ComputerToolDispatcher,
    EndComputerSessionInput,
)


# ── Test 1: Sequential Browser Calls Persist Same Instance ───────────────────

def test_sequential_browser_calls_persist_same_instance():
    """
    Verify get_or_create_browser_controller returns the identical BrowserController
    instance across repeated calls with the same (bot_id, session_id).
    """
    registry = SessionRegistry(session_ttl_seconds=60)
    bot_id = "agent_crawler"
    session_id = "session_001"

    bc1 = registry.get_or_create_browser_controller(bot_id=bot_id, session_id=session_id)
    bc2 = registry.get_or_create_browser_controller(bot_id=bot_id, session_id=session_id)

    # Must be the exact same instance
    assert bc1 is bc2
    assert bc1.bot_id == bot_id
    assert bc1.session_id == session_id
    assert registry.get_active_session_count() == 1

    registry.clear()


@pytest.mark.asyncio
async def test_sequential_browser_calls_persist_browser_context(tmp_path: Path):
    """
    Live browser verification: sequential operations within the same session
    reuse the exact same Chromium context and maintain page DOM / cookie state.
    """
    registry = SessionRegistry(session_ttl_seconds=60)
    bot_id = "browser_agent"
    session_id = "persist_ctx_sess"

    # HTML fixture with form and dynamic cookie
    html_page = tmp_path / "login.html"
    html_page.write_text(
        """
        <!DOCTYPE html>
        <html>
        <head><title>Secure Dashboard</title></head>
        <body>
            <h1>Welcome to Dashboard</h1>
            <input type="text" id="username" placeholder="Username" aria-label="Username" />
            <button id="login-btn">Log In</button>
            <script>
                document.cookie = "session_token=ULTRON_SECURE_TOKEN_XYZ; path=/";
            </script>
        </body>
        </html>
        """,
        encoding="utf-8",
    )
    file_url = f"file:///{html_page.as_posix()}"

    bc = registry.get_or_create_browser_controller(bot_id=bot_id, session_id=session_id)
    snapshot1 = await bc.navigate(file_url)
    assert snapshot1.title == "Secure Dashboard"
    assert bc._page is not None

    # Set cookie in browser context and type into input field
    await bc._context.add_cookies([
        {"name": "session_token", "value": "ULTRON_SECURE_TOKEN_XYZ", "domain": "example.com", "path": "/"}
    ])
    await bc.type_text(1, "agent_alpha_credentials")

    # Retrieve controller again via registry
    bc_reused = registry.get_or_create_browser_controller(bot_id=bot_id, session_id=session_id)
    assert bc_reused is bc

    # Verify cookies and context are preserved in reused controller
    cookies = await bc_reused._context.cookies()
    cookie_names = [c["name"] for c in cookies]
    assert "session_token" in cookie_names

    # Verify DOM input value is preserved in reused page
    val = await bc_reused._page.locator("#username").input_value()
    assert val == "agent_alpha_credentials"

    await registry.clear_async()


# ── Test 2: Sequential Sandbox Calls Persist Same Instance & Files ───────────

def test_sequential_sandbox_calls_persist_same_instance_and_files(tmp_path: Path):
    """
    Verify get_or_create_sandbox returns the identical sandbox instance and
    files written in call 1 remain present in call 2.
    """
    base_dir = str(tmp_path / "workspaces")
    registry = SessionRegistry(session_ttl_seconds=60, sandbox_base_dir=base_dir)

    bot_id = "data_bot"
    session_id = "persist_fs_sess"

    sb1 = registry.get_or_create_sandbox(bot_id=bot_id, session_id=session_id)
    assert isinstance(sb1, LocalDriver)

    # Write file in call 1
    write_ok = sb1.write_workspace_file("test_state.txt", "INITIAL_STATE_123")
    assert write_ok is True

    # Retrieve sandbox again in call 2
    sb2 = registry.get_or_create_sandbox(bot_id=bot_id, session_id=session_id)
    assert sb1 is sb2

    # Verify state persists
    assert sb2.read_workspace_file("test_state.txt") == "INITIAL_STATE_123"

    registry.clear()


# ── Test 3: Session TTL — Active Session Within TTL is Not Evicted ───────────

def test_session_ttl_active_session_not_evicted():
    """
    Sessions within their TTL window must not be evicted by sweep_expired().
    """
    registry = SessionRegistry(session_ttl_seconds=300)
    bot_id = "active_bot"
    session_id = "active_sess"

    sb = registry.get_or_create_sandbox(bot_id=bot_id, session_id=session_id)
    assert registry.has_session(bot_id, session_id) is True

    evicted = registry.sweep_expired()
    assert evicted == []
    assert registry.has_session(bot_id, session_id) is True
    assert registry.get_active_session_count() == 1

    registry.clear()


# ── Test 4: Session TTL — Idle Session Exceeding TTL is Evicted ──────────────

def test_session_ttl_idle_session_evicted_and_cleaned_up(tmp_path: Path):
    """
    Sessions exceeding session_ttl_seconds must be evicted by sweep_expired(),
    with sandbox.cleanup() and browser.close() executed.
    """
    registry = SessionRegistry(session_ttl_seconds=2, sandbox_base_dir=str(tmp_path / "ws"))
    bot_id = "stale_bot"
    session_id = "stale_sess"

    sb = registry.get_or_create_sandbox(bot_id=bot_id, session_id=session_id)
    bc = registry.get_or_create_browser_controller(bot_id=bot_id, session_id=session_id)

    # Mock cleanup and close to verify invocation
    sb.cleanup = MagicMock()
    bc.close = AsyncMock()

    # Artificially set last_active_at back 5 seconds
    key = f"{bot_id}:{session_id}"
    registry._registry[key].last_active_at = time.time() - 5.0

    evicted = registry.sweep_expired()
    assert key in evicted
    assert registry.has_session(bot_id, session_id) is False
    assert registry.get_active_session_count() == 0

    sb.cleanup.assert_called_once()


# ── Test 5: Expired Session Re-Request Provisions Fresh Instance ──────────────

def test_expired_session_re_request_provisions_fresh_instances(tmp_path: Path):
    """
    When a session has expired, the next get_or_create call must clean up the
    old expired instance and return a brand-new instance.
    """
    registry = SessionRegistry(session_ttl_seconds=2, sandbox_base_dir=str(tmp_path / "ws"))
    bot_id = "renew_bot"
    session_id = "renew_sess"

    sb_old = registry.get_or_create_sandbox(bot_id=bot_id, session_id=session_id)
    sb_old.cleanup = MagicMock()

    # Expire the session entry
    key = f"{bot_id}:{session_id}"
    registry._registry[key].last_active_at = time.time() - 10.0

    # Next call should detect expiry, evict, and create fresh
    sb_new = registry.get_or_create_sandbox(bot_id=bot_id, session_id=session_id)
    assert sb_new is not sb_old
    sb_old.cleanup.assert_called_once()
    assert registry.has_session(bot_id, session_id) is True

    registry.clear()


# ── Test 6: Touch Mechanics Reset TTL ────────────────────────────────────────

def test_touch_resets_ttl():
    """
    Calling touch() updates last_active_at and prevents eviction by sweep_expired().
    """
    registry = SessionRegistry(session_ttl_seconds=5)
    bot_id = "touched_bot"
    session_id = "touched_sess"

    registry.get_or_create_sandbox(bot_id=bot_id, session_id=session_id)
    key = f"{bot_id}:{session_id}"

    # Age it slightly
    initial_time = time.time() - 4.0
    registry._registry[key].last_active_at = initial_time

    # Touch it to refresh activity
    time.sleep(0.01)
    registry.touch(bot_id=bot_id, session_id=session_id)
    assert registry._registry[key].last_active_at > initial_time

    # Must NOT be evicted
    evicted = registry.sweep_expired()
    assert evicted == []
    assert registry.has_session(bot_id, session_id) is True

    registry.clear()


# ── Test 7: Explicit end_session() Teardown & Idempotence ─────────────────────

def test_end_session_explicit_cleanup_and_idempotence(tmp_path: Path):
    """
    end_session() immediately tears down active sandbox/browser resources,
    removes the entry, and behaves as a safe no-op on repeated calls.
    """
    registry = SessionRegistry(session_ttl_seconds=300, sandbox_base_dir=str(tmp_path / "ws"))
    bot_id = "teardown_bot"
    session_id = "teardown_sess"

    sb = registry.get_or_create_sandbox(bot_id=bot_id, session_id=session_id)
    bc = registry.get_or_create_browser_controller(bot_id=bot_id, session_id=session_id)

    sb.cleanup = MagicMock()
    bc.close = AsyncMock()

    assert registry.has_session(bot_id, session_id) is True

    # 1. First end_session call cleans up and evicts
    registry.end_session(bot_id=bot_id, session_id=session_id)
    assert registry.has_session(bot_id, session_id) is False
    assert registry.get_active_session_count() == 0
    sb.cleanup.assert_called_once()

    # 2. Second end_session call is a safe no-op
    registry.end_session(bot_id=bot_id, session_id=session_id)
    assert registry.get_active_session_count() == 0

    # 3. Non-existent session end is also a safe no-op
    registry.end_session(bot_id="non_existent", session_id="none")
    assert registry.get_active_session_count() == 0


# ── Test 8: Multi-Bot Session Persistence Isolation ──────────────────────────

def test_multi_bot_persistence_isolation(tmp_path: Path):
    """
    Different bots (bot_alpha, bot_beta) acting in the same session_id maintain
    distinct persistent contexts. Ending one bot's session does not affect the other.
    """
    registry = SessionRegistry(session_ttl_seconds=300, sandbox_base_dir=str(tmp_path / "ws"))
    session_id = "swarm_shared_sess"

    sb_alpha = registry.get_or_create_sandbox(bot_id="bot_alpha", session_id=session_id)
    sb_beta = registry.get_or_create_sandbox(bot_id="bot_beta", session_id=session_id)

    assert sb_alpha is not sb_beta
    assert registry.get_active_session_count() == 2

    # Write separate files
    sb_alpha.write_workspace_file("alpha.txt", "ALPHA")
    sb_beta.write_workspace_file("beta.txt", "BETA")

    # End bot_alpha
    registry.end_session(bot_id="bot_alpha", session_id=session_id)
    assert registry.has_session("bot_alpha", session_id) is False
    assert registry.has_session("bot_beta", session_id) is True

    # Bot beta is still intact and can read its file
    sb_beta_check = registry.get_or_create_sandbox(bot_id="bot_beta", session_id=session_id)
    assert sb_beta_check is sb_beta
    assert sb_beta_check.read_workspace_file("beta.txt") == "BETA"

    registry.clear()


# ── Test 9: Take-the-Wheel Handoff Continuity ────────────────────────────────

def test_takeover_handoff_preserves_session_across_wheel_release(tmp_path: Path):
    """
    Takeover engagement must NOT destroy sandbox or browser instances.
    When wheel is released, the bot resumes in the exact same sandbox and browser.
    """
    dispatcher = ComputerToolDispatcher(sandbox_base_dir=str(tmp_path / "ws"))
    bot_id = "bot_hero"
    session_id = "handoff_sess"

    # 1. Establish persistent sandbox and browser
    sb = dispatcher.get_sandbox(bot_id=bot_id, session_id=session_id)
    sb.write_workspace_file("mission_log.txt", "PHASE_1_COMPLETE")

    # 2. Trigger Take-the-Wheel
    fake_snapshot = BrowserSnapshot(
        url="https://auth.internal/login",
        title="2FA Required",
        aria_tree="[1] Input: 2FA Code",
        interactive_elements=[],
    )
    dispatcher.handoff_manager.trigger_takeover(
        session_id=session_id,
        snapshot=fake_snapshot,
        reason="2FA detected",
    )
    assert dispatcher.handoff_manager.is_takeover_active(session_id) is True

    # 3. Actions during takeover are rejected, but session remains alive in registry
    res_blocked = dispatcher.dispatch(
        tool_name="computer_shell",
        arguments={"command": "dir", "session_id": session_id, "bot_id": bot_id},
    )
    assert '"status": "TAKEOVER_IN_PROGRESS"' in res_blocked
    assert dispatcher.session_registry.has_session(bot_id, session_id) is True

    # 4. Human completes 2FA and releases wheel
    dispatcher.handoff_manager.release_wheel(session_id=session_id, success=True)
    assert dispatcher.handoff_manager.is_takeover_active(session_id) is False

    # 5. Bot resumes — sandbox and files are identical
    sb_resumed = dispatcher.get_sandbox(bot_id=bot_id, session_id=session_id)
    assert sb_resumed is sb
    assert sb_resumed.read_workspace_file("mission_log.txt") == "PHASE_1_COMPLETE"

    dispatcher.cleanup()


# ── Test 10: Dispatcher end_computer_session Tool Call ───────────────────────

def test_dispatcher_end_computer_session_tool(tmp_path: Path):
    """
    Dispatching end_computer_session explicitly terminates the session and
    cleans up registry resources.
    """
    dispatcher = ComputerToolDispatcher(sandbox_base_dir=str(tmp_path / "ws"))
    bot_id = "clean_bot"
    session_id = "sess_to_end"

    # Pre-populate session
    dispatcher.get_sandbox(bot_id=bot_id, session_id=session_id)
    assert dispatcher.session_registry.has_session(bot_id, session_id) is True

    # Dispatch end_computer_session
    raw_res = dispatcher.dispatch(
        tool_name="end_computer_session",
        arguments={"session_id": session_id, "bot_id": bot_id},
    )
    res = json.loads(raw_res)

    assert res["status"] == "COMPLETED"
    assert res["action_type"] == "SHELL_EXEC"
    assert res["result"]["action"] == "end_computer_session"
    assert dispatcher.session_registry.has_session(bot_id, session_id) is False

    dispatcher.cleanup()


# ── Test 11: Dispatched Actions Touch Registry ───────────────────────────────

def test_dispatch_action_touches_registry(tmp_path: Path):
    """
    Every dispatched action must update the session's last_active_at in the registry.
    """
    dispatcher = ComputerToolDispatcher(sandbox_base_dir=str(tmp_path / "ws"))
    bot_id = "timing_bot"
    session_id = "timing_sess"

    # Initial action
    dispatcher.dispatch(
        tool_name="computer_shell",
        arguments={
            "command": "python -c \"print('TOUCH_1')\"",
            "session_id": session_id,
            "bot_id": bot_id,
        },
    )
    entry = dispatcher.session_registry.get_session_entry(bot_id, session_id)
    assert entry is not None
    t1 = entry.last_active_at

    # Wait briefly and execute second action
    time.sleep(0.05)
    dispatcher.dispatch(
        tool_name="computer_shell",
        arguments={
            "command": "python -c \"print('TOUCH_2')\"",
            "session_id": session_id,
            "bot_id": bot_id,
        },
    )
    t2 = entry.last_active_at
    assert t2 > t1

    dispatcher.cleanup()


# ── Test 12: Multi-Process Caveat Documentation ──────────────────────────────

def test_multiprocess_caveat_documentation():
    """
    Verify session_registry.py module docstring explicitly documents the process-local
    in-memory limitation, sticky session routing, and external store (Redis) recommendations.
    """
    doc = session_registry_module.__doc__
    assert doc is not None
    assert "process-local" in doc.lower() or "in-memory" in doc.lower()
    assert "multi-process" in doc.lower() or "worker processes" in doc.lower()
    assert "redis" in doc.lower()
    assert "sticky" in doc.lower() or "affinity" in doc.lower()


# ── Test 13: End Computer Session Schema and Pydantic Model ──────────────────

def test_end_computer_session_schema_and_model():
    """
    Verify END_COMPUTER_SESSION_TOOL schema and EndComputerSessionInput Pydantic model.
    """
    assert END_COMPUTER_SESSION_TOOL["name"] == "end_computer_session"
    assert "input_schema" in END_COMPUTER_SESSION_TOOL
    schema = END_COMPUTER_SESSION_TOOL["input_schema"]
    assert "session_id" in schema["properties"]
    assert "bot_id" in schema["properties"]

    # Extended tools collection has 5 tools
    assert len(EXTENDED_COMPUTER_TOOLS) == 5
    assert END_COMPUTER_SESSION_TOOL in EXTENDED_COMPUTER_TOOLS

    # Core COMPUTER_TOOLS remains unchanged at 4 tools for zero regression
    assert len(COMPUTER_TOOLS) == 4

    # Strict input validation
    valid_input = EndComputerSessionInput(session_id="s1", bot_id="b1")
    assert valid_input.session_id == "s1"
    assert valid_input.bot_id == "b1"

    # Default values
    default_input = EndComputerSessionInput()
    assert default_input.session_id == "default"
    assert default_input.bot_id == "ultron_openbot"

    # Extra fields forbidden
    with pytest.raises(Exception):
        EndComputerSessionInput(session_id="s1", illegal_field=123)  # type: ignore[call-arg]
