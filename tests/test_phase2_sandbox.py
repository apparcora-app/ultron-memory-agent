"""
test_phase2_sandbox.py — Verification Test Suite for OpenBot Phase 2: Isolated Sandbox Drivers.

Tests:
  1. Directory traversal blocking: writing to ../../escape.txt raises PermissionError.
  2. Symlink escape blocking: symlink/junction created inside sandbox pointing outside is rejected.
  3. Basic command execution & file persistence within the designated sandbox path.
  4. AST validation interception: Python commands with dangerous imports/calls trigger ASTSecurityViolation.
  5. Dynamic Sandbox Factory: fallback to LocalDriver without E2B key, and E2BDriver provisioning when configured.
  6. Binary and string file read/write integrity.
  7. Non-existent file reads raise FileNotFoundError.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure ultron-memory-agent root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from guardrails.ast_sandbox import ASTSecurityViolation
from ultron.execution.drivers.base_sandbox import BaseSandbox
from ultron.execution.drivers.e2b_driver import E2BDriver
from ultron.execution.drivers.local_driver import LocalDriver
from ultron.execution.drivers.sandbox_factory import get_sandbox


# ── Test 1: Directory Traversal Defense ───────────────────────────────────────

@pytest.mark.parametrize(
    "traversal_path",
    [
        "../../escape.txt",
        "../escape.txt",
        "dir/../../../outside.txt",
        "..\\..\\escape_win.txt",
        "nested/../../../../etc/passwd",
    ],
)
def test_directory_traversal_blocking_on_write(tmp_path: Path, traversal_path: str):
    """
    Writing to any path containing '..' must raise a PermissionError and reject the operation.
    """
    driver = LocalDriver(session_id="test_trav_write", base_dir=str(tmp_path))

    with pytest.raises(PermissionError) as exc_info:
        driver.write_workspace_file(traversal_path, "malicious payload")

    assert "traversal" in str(exc_info.value).lower() or ".." in str(exc_info.value)


@pytest.mark.parametrize(
    "traversal_path",
    [
        "../../escape.txt",
        "../secret.key",
        "folder/../../shadow",
    ],
)
def test_directory_traversal_blocking_on_read(tmp_path: Path, traversal_path: str):
    """
    Reading from any path containing '..' must raise a PermissionError and reject the operation.
    """
    driver = LocalDriver(session_id="test_trav_read", base_dir=str(tmp_path))

    with pytest.raises(PermissionError) as exc_info:
        driver.read_workspace_file(traversal_path)

    assert "traversal" in str(exc_info.value).lower() or ".." in str(exc_info.value)


# ── Test 2: Symlink Escape Defense ───────────────────────────────────────────

def test_symlink_escape_blocking_on_read_and_write(tmp_path: Path):
    """
    A symlink or junction created inside the sandbox pointing outside must be rejected
    on both read and write operations.
    """
    sandbox_base = tmp_path / "workspaces"
    outside_dir = tmp_path / "outside_host_dir"
    outside_dir.mkdir(parents=True, exist_ok=True)

    # Place a secret outside the sandbox
    host_secret_file = outside_dir / "host_secret.txt"
    host_secret_file.write_text("SUPER_SECRET_HOST_DATA", encoding="utf-8")

    driver = LocalDriver(session_id="test_symlink_escape", base_dir=str(sandbox_base))
    symlink_path = driver.workspace_dir / "planted_outside_link"

    # Create link pointing outside: try symlink, then Windows junction
    link_created = False
    try:
        os.symlink(str(outside_dir), str(symlink_path), target_is_directory=True)
        link_created = True
    except (OSError, NotImplementedError):
        if os.name == "nt":
            try:
                import _winapi
                _winapi.CreateJunction(str(outside_dir), str(symlink_path))
                link_created = True
            except Exception:
                pass

    if link_created:
        # 1. Attempt reading through the planted symlink
        with pytest.raises(PermissionError) as exc_read:
            driver.read_workspace_file("planted_outside_link/host_secret.txt")
        assert "escape" in str(exc_read.value).lower() or "outside sandbox" in str(exc_read.value).lower()

        # 2. Attempt writing through the planted symlink
        with pytest.raises(PermissionError) as exc_write:
            driver.write_workspace_file("planted_outside_link/hacked.txt", "corrupted")
        assert "escape" in str(exc_write.value).lower() or "outside sandbox" in str(exc_write.value).lower()

        # Verify host file was not touched
        assert not (outside_dir / "hacked.txt").exists()
    else:
        # Fallback for environments where symlink creation is restricted: mock realpath breakout
        with patch("os.path.realpath") as mock_realpath:
            # Simulate target resolving outside sandbox root
            mock_realpath.side_effect = lambda p: str(outside_dir / "mock_file.txt") if "planted_link" in str(p) else str(p)
            with pytest.raises(PermissionError):
                driver.read_workspace_file("planted_link/secret.txt")


# ── Test 3: Command Execution & File Persistence ──────────────────────────────

def test_basic_command_execution_and_file_persistence(tmp_path: Path):
    """
    Test command execution inside the designated sandbox and verify file persistence.
    """
    driver = LocalDriver(session_id="test_exec_persist", base_dir=str(tmp_path))

    # 1. Write file to workspace
    rel_path = "reports/quarterly_summary.txt"
    content = "Revenue: $1,250,000\nEBITDA: $450,000"
    success = driver.write_workspace_file(rel_path, content)
    assert success is True

    # 2. Verify file persisted on host at expected scoped location
    expected_host_file = driver.workspace_dir / "reports" / "quarterly_summary.txt"
    assert expected_host_file.exists()
    assert expected_host_file.read_text(encoding="utf-8") == content

    # 3. Read file back through driver
    read_back = driver.read_workspace_file(rel_path)
    assert read_back == content

    # 4. Execute command in workspace directory
    res = driver.execute_command("dir /b" if os.name == "nt" else "ls")

    assert res["exit_code"] == 0
    assert "reports" in res["stdout"]


# ── Test 4: AST Validation Interception for Python Commands ───────────────────

def test_ast_validation_blocks_dangerous_python_execution(tmp_path: Path):
    """
    Executing Python scripts or inline commands with dangerous imports/calls
    must be statically intercepted by ASTValidator and raise ASTSecurityViolation.
    """
    driver = LocalDriver(session_id="test_ast_guard", base_dir=str(tmp_path))

    # 1. Dangerous inline python command (eval/os)
    dangerous_cmd = 'python -c "import os; os.system(\'whoami\')"'
    with pytest.raises(ASTSecurityViolation) as exc_inline:
        driver.execute_command(dangerous_cmd)
    assert "AST SECURITY VIOLATION" in str(exc_inline.value)

    # 2. Dangerous python script file
    bad_script_rel = "scripts/exploit.py"
    driver.write_workspace_file(bad_script_rel, "import subprocess\nsubprocess.run(['dir'])")

    with pytest.raises(ASTSecurityViolation) as exc_script:
        driver.execute_command(f"python {bad_script_rel}")
    assert "AST SECURITY VIOLATION" in str(exc_script.value)


def test_ast_validation_permits_safe_python_execution(tmp_path: Path):
    """
    Safe Python scripts using whitelisted math/json libraries should pass AST validation.
    """
    driver = LocalDriver(session_id="test_ast_safe", base_dir=str(tmp_path))

    safe_script_rel = "safe_calc.py"
    driver.write_workspace_file(safe_script_rel, "import math, json\nprint(json.dumps({'pi': round(math.pi, 2)}))")

    res = driver.execute_command(f"python {safe_script_rel}")
    assert res["exit_code"] == 0
    assert '"pi": 3.14' in res["stdout"]


# ── Test 5: Dynamic Sandbox Factory & Resilient Fallback ───────────────────────

def test_sandbox_factory_fallback_to_local_driver(tmp_path: Path):
    """
    When E2B_API_KEY is not set, factory safely falls back and returns LocalDriver.
    """
    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("E2B_API_KEY", None)
        sandbox = get_sandbox(session_id="sess_fallback", base_dir=str(tmp_path))
        assert isinstance(sandbox, LocalDriver)
        assert sandbox.session_id == "sess_fallback"
        assert sandbox.workspace_dir.exists()


def test_sandbox_factory_provisions_e2b_when_key_present():
    """
    When E2B_API_KEY is present and SDK is available, factory provisions E2BDriver.
    """
    mock_e2b_instance = MagicMock()
    mock_e2b_class = MagicMock()
    mock_e2b_class.create.return_value = mock_e2b_instance

    with patch.dict(os.environ, {"E2B_API_KEY": "e2b_test_mock_api_key"}):
        with patch("ultron.execution.drivers.e2b_driver.E2BSandbox", mock_e2b_class):
            sandbox = get_sandbox(session_id="sess_e2b_active")
            assert isinstance(sandbox, E2BDriver)
            assert sandbox.session_id == "sess_e2b_active"
            assert sandbox.cwd == "/workspace"
            mock_e2b_class.create.assert_called_once()


# ── Test 6: Binary File Read and Write ────────────────────────────────────────

def test_binary_file_read_and_write(tmp_path: Path):
    """
    Verify writing and reading binary payloads (e.g. image bytes).
    """
    driver = LocalDriver(session_id="test_binary_io", base_dir=str(tmp_path))

    raw_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    driver.write_workspace_file("assets/image.png", raw_bytes)

    host_file = driver.workspace_dir / "assets" / "image.png"
    assert host_file.exists()
    assert host_file.read_bytes() == raw_bytes


# ── Test 7: Non-Existent File Read ────────────────────────────────────────────

def test_read_non_existent_file_raises_not_found(tmp_path: Path):
    """
    Reading a file that does not exist within the sandbox workspace raises FileNotFoundError.
    """
    driver = LocalDriver(session_id="test_missing_file", base_dir=str(tmp_path))

    with pytest.raises(FileNotFoundError):
        driver.read_workspace_file("non_existent_data.json")


# ── Test 8: Context Manager Teardown ──────────────────────────────────────────

def test_sandbox_context_manager_cleanup(tmp_path: Path):
    """
    Verify BaseSandbox context manager automatically triggers cleanup().
    """
    with LocalDriver(session_id="test_ctx_mgr", base_dir=str(tmp_path)) as sandbox:
        assert sandbox._is_cleaned_up is False
        sandbox.write_workspace_file("file.txt", "active")

    assert sandbox._is_cleaned_up is True
    with pytest.raises(RuntimeError):
        sandbox.execute_command("echo hello")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
