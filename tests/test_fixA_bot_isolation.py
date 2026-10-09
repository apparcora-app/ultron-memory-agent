"""
test_fixA_bot_isolation.py — Verification Test Suite for OpenBot Fix A: Bot-Scoped Isolation.

Tests:
  1. Two different bot_ids with the same session_id receive distinct sandbox instances with distinct workspace paths.
  2. A file written by bot_id="alpha" is not readable by bot_id="beta" in the same session.
  3. LocalDriver path sanitization rejects bot_id or session_id containing '/', '..', or other path-control characters.
  4. Composite isolation key derivation f"{bot_id}:{session_id}" is consistent across drivers.
  5. E2BDriver tags cloud microVMs with composite metadata (bot_id, session_id, composite_key).
  6. ComputerToolDispatcher routes commands and file operations to bot-scoped sandboxes without crosstalk.
  7. BrowserController isolation: contexts are scoped per (bot_id, session_id).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure ultron-memory-agent root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ultron.execution.drivers.base_sandbox import BaseSandbox
from ultron.execution.drivers.browser_controller import BrowserController
from ultron.execution.drivers.e2b_driver import E2BDriver
from ultron.execution.drivers.local_driver import LocalDriver, sanitize_identifier
from ultron.execution.drivers.sandbox_factory import get_sandbox
from ultron.execution.tool_bridge import ComputerToolDispatcher


# ── Test 1: Distinct Sandbox Instances and Workspace Paths for Same Session ───

def test_distinct_sandboxes_and_paths_for_different_bots_in_same_session(tmp_path: Path):
    """
    Two different bot_ids with the same session_id must receive two distinct
    sandbox instances with two distinct workspace paths.
    """
    session_id = "shared_mission_alpha"
    base_dir = str(tmp_path / "workspaces")

    sb_alpha = get_sandbox(bot_id="agent_recon", session_id=session_id, base_dir=base_dir)
    sb_beta = get_sandbox(bot_id="agent_analyst", session_id=session_id, base_dir=base_dir)

    # 1. Instances must be completely distinct
    assert sb_alpha is not sb_beta
    assert isinstance(sb_alpha, LocalDriver)
    assert isinstance(sb_beta, LocalDriver)

    # 2. Scoped workspace directories must be distinct
    assert sb_alpha.workspace_dir != sb_beta.workspace_dir
    assert sb_alpha.workspace_dir.exists()
    assert sb_beta.workspace_dir.exists()

    # 3. Workspace naming must follow sandbox_<bot_id>_<session_id>
    assert sb_alpha.workspace_dir.name == "sandbox_agent_recon_shared_mission_alpha"
    assert sb_beta.workspace_dir.name == "sandbox_agent_analyst_shared_mission_alpha"

    # 4. Composite isolation keys must match f"{bot_id}:{session_id}"
    assert sb_alpha.isolation_key == "agent_recon:shared_mission_alpha"
    assert sb_beta.isolation_key == "agent_analyst:shared_mission_alpha"
    assert sb_alpha.bot_id == "agent_recon"
    assert sb_beta.bot_id == "agent_analyst"
    assert sb_alpha.session_id == session_id
    assert sb_beta.session_id == session_id


# ── Test 2: File Isolation Between Bots in Same Session ───────────────────────

def test_file_written_by_one_bot_not_readable_by_another_bot(tmp_path: Path):
    """
    A file written by bot_id='alpha' must not be readable via get_sandbox(bot_id='beta', session_id=<same session>).
    """
    session_id = "cross_bot_leak_test"
    base_dir = str(tmp_path / "workspaces")

    sb_alpha = get_sandbox(bot_id="alpha", session_id=session_id, base_dir=base_dir)
    sb_beta = get_sandbox(bot_id="beta", session_id=session_id, base_dir=base_dir)

    # Bot Alpha writes sensitive financial data
    file_name = "secret_ledger.json"
    content = '{"revenue": 1000000, "status": "classified"}'
    write_ok = sb_alpha.write_workspace_file(file_name, content)
    assert write_ok is True

    # Verify file physically exists in Alpha's workspace
    assert (sb_alpha.workspace_dir / file_name).exists()
    assert sb_alpha.read_workspace_file(file_name) == content

    # Verify file does NOT exist in Beta's workspace
    assert not (sb_beta.workspace_dir / file_name).exists()

    # Attempting to read Alpha's file from Beta's sandbox must raise FileNotFoundError
    with pytest.raises(FileNotFoundError):
        sb_beta.read_workspace_file(file_name)

    # Command execution isolation: Alpha creates a file via shell, Beta cannot see it
    sb_alpha.execute_command("echo secret_payload > alpha_out.txt")
    assert (sb_alpha.workspace_dir / "alpha_out.txt").exists()
    assert not (sb_beta.workspace_dir / "alpha_out.txt").exists()


# ── Test 3: Path Sanitization Rejects Path-Control Characters ─────────────────

@pytest.mark.parametrize("invalid_id,name", [
    ("../escape", "bot_id"),
    ("..\\escape", "bot_id"),
    ("bot/subfolder", "bot_id"),
    ("bot\\subfolder", "bot_id"),
    ("bot..escape", "bot_id"),
    ("bot;rm -rf", "bot_id"),
    ("bot$VAR", "bot_id"),
    ("bot name with space", "bot_id"),
    ("bot\x00null", "bot_id"),
    ("", "bot_id"),
    ("   ", "bot_id"),
    ("../escape_sess", "session_id"),
    ("..\\escape_sess", "session_id"),
    ("session/leak", "session_id"),
    ("session\\leak", "session_id"),
    ("session*all", "session_id"),
    ("session|pipe", "session_id"),
    ("", "session_id"),
])
def test_path_sanitization_rejects_path_control_characters(
    tmp_path: Path,
    invalid_id: str,
    name: str,
):
    """
    Verify the LocalDriver path-sanitization rejects a bot_id or session_id
    containing /, .., or other path-control characters with a ValueError,
    preventing path-traversal or injection via crafted IDs.
    """
    base_dir = str(tmp_path / "workspaces")

    if name == "bot_id":
        with pytest.raises(ValueError) as exc_info:
            get_sandbox(bot_id=invalid_id, session_id="valid_session", base_dir=base_dir)
        assert "disallowed" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()

        # Direct sanitizer check
        with pytest.raises(ValueError):
            sanitize_identifier(invalid_id, "bot_id")
    else:
        with pytest.raises(ValueError) as exc_info:
            get_sandbox(bot_id="valid_bot", session_id=invalid_id, base_dir=base_dir)
        assert "disallowed" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()

        # Direct sanitizer check
        with pytest.raises(ValueError):
            sanitize_identifier(invalid_id, "session_id")


def test_path_sanitization_accepts_valid_alphanumeric_and_separators():
    """
    Verify that alphanumeric characters, dashes, and underscores are permitted.
    """
    assert sanitize_identifier("bot-123_alpha", "bot_id") == "bot-123_alpha"
    assert sanitize_identifier("SESSION_99-x", "session_id") == "SESSION_99-x"
    assert sanitize_identifier("swarm_agent_007", "bot_id") == "swarm_agent_007"


# ── Test 4: E2BDriver Composite Tagging and Driver State ──────────────────────

def test_e2b_driver_composite_tagging():
    """
    Verify E2BDriver sets composite isolation key f"{bot_id}:{session_id}"
    and passes metadata tags when provisioning microVMs.
    """
    mock_e2b_instance = MagicMock()
    mock_e2b_class = MagicMock()
    mock_e2b_class.create.return_value = mock_e2b_instance

    with patch.dict(os.environ, {"E2B_API_KEY": "e2b_test_mock_key"}):
        with patch("ultron.execution.drivers.e2b_driver.E2BSandbox", mock_e2b_class):
            sandbox = get_sandbox(bot_id="worker_bot_1", session_id="e2b_sess_42")

            assert isinstance(sandbox, E2BDriver)
            assert sandbox.bot_id == "worker_bot_1"
            assert sandbox.session_id == "e2b_sess_42"
            assert sandbox.isolation_key == "worker_bot_1:e2b_sess_42"
            assert sandbox.composite_key == "worker_bot_1:e2b_sess_42"

            mock_e2b_class.create.assert_called_once()
            call_kwargs = mock_e2b_class.create.call_args[1]
            assert "metadata" in call_kwargs
            metadata = call_kwargs["metadata"]
            assert metadata["bot_id"] == "worker_bot_1"
            assert metadata["session_id"] == "e2b_sess_42"
            assert metadata["composite_key"] == "worker_bot_1:e2b_sess_42"


# ── Test 5: ComputerToolDispatcher Multi-Bot Scoped Execution ────────────────

def test_tool_dispatcher_multi_bot_scoped_execution(tmp_path: Path):
    """
    Verify ComputerToolDispatcher maintains separate sandboxes and workspaces
    when multiple bots dispatch actions within the same session.
    """
    base_dir = str(tmp_path / "workspaces")
    dispatcher = ComputerToolDispatcher(sandbox_base_dir=base_dir)

    session_id = "concurrent_swarm_session"

    # Bot A writes a file via fs_write tool
    res_a = dispatcher.dispatch(
        tool_name="fs_write",
        arguments={
            "path": "bot_a_file.txt",
            "content": "DATA_A",
            "session_id": session_id,
            "bot_id": "bot_a",
        },
    )
    assert '"status": "COMPLETED"' in res_a

    # Bot B writes a file via fs_write tool
    res_b = dispatcher.dispatch(
        tool_name="fs_write",
        arguments={
            "path": "bot_b_file.txt",
            "content": "DATA_B",
            "session_id": session_id,
            "bot_id": "bot_b",
        },
    )
    assert '"status": "COMPLETED"' in res_b

    # Verify shell execution runs isolated per bot
    res_shell_a = dispatcher.dispatch(
        tool_name="computer_shell",
        arguments={
            "command": "python -c \"print('RUN_ALPHA')\"",
            "session_id": session_id,
            "bot_id": "bot_a",
        },
    )
    assert "RUN_ALPHA" in res_shell_a

    # Verify sandboxes are cached under composite keys in dispatcher
    assert "bot_a:concurrent_swarm_session" in dispatcher._sandboxes
    assert "bot_b:concurrent_swarm_session" in dispatcher._sandboxes

    sb_a = dispatcher.get_sandbox(bot_id="bot_a", session_id=session_id)
    sb_b = dispatcher.get_sandbox(bot_id="bot_b", session_id=session_id)

    assert sb_a is not sb_b
    assert sb_a.read_workspace_file("bot_a_file.txt") == "DATA_A"
    assert sb_b.read_workspace_file("bot_b_file.txt") == "DATA_B"

    # Cross-read raises FileNotFoundError
    with pytest.raises(FileNotFoundError):
        sb_a.read_workspace_file("bot_b_file.txt")

    with pytest.raises(FileNotFoundError):
        sb_b.read_workspace_file("bot_a_file.txt")

    dispatcher.cleanup()


# ── Test 6: Browser Scoping per (bot_id, session_id) ─────────────────────────

def test_browser_controller_scoped_per_bot_and_session():
    """
    Verify BrowserController instances are scoped per (bot_id, session_id)
    and never shared across different bots in the same session.
    """
    dispatcher = ComputerToolDispatcher()
    session_id = "shared_browser_sess"

    bc_alpha = dispatcher.get_browser_controller(bot_id="browser_bot_1", session_id=session_id)
    bc_beta = dispatcher.get_browser_controller(bot_id="browser_bot_2", session_id=session_id)

    assert bc_alpha is not bc_beta
    assert bc_alpha.isolation_key == f"browser_bot_1:{session_id}"
    assert bc_beta.isolation_key == f"browser_bot_2:{session_id}"
    assert bc_alpha.bot_id == "browser_bot_1"
    assert bc_beta.bot_id == "browser_bot_2"

    assert "browser_bot_1:shared_browser_sess" in dispatcher._browser_controllers
    assert "browser_bot_2:shared_browser_sess" in dispatcher._browser_controllers

    dispatcher.cleanup()
