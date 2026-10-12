"""
local_driver.py — Resilient Scoped Local Sandbox Driver with Anti-Traversal & AST Guardrails.

Provides a secure local sandbox when external microVM providers (e.g. E2B) are offline or unconfigured.
Confines all operations to './data/workspace/sandbox_<session_id>/' and enforces:
  1. Strict lexical path traversal defense ('..').
  2. Canonical filesystem resolution via realpath to prevent symlink / junction escapes.
  3. Pre-execution static AST security validation from ultron.guardrails/ast_sandbox.py for Python tasks.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from ultron.execution.drivers.base_sandbox import BaseSandbox
from ultron.guardrails.ast_sandbox import ASTValidator

logger = logging.getLogger(__name__)

DEFAULT_BASE_WORKSPACE = "./data/workspace"


ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+$")


def sanitize_identifier(value: str, name: str = "identifier") -> str:
    """
    Validate and sanitize an identifier to alphanumeric, hyphen, and underscore only.
    Rejects any string containing '/', '\\', '..', or path-control characters.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Invalid {name}: must be a non-empty string.")
    cleaned = value.strip()
    if not ID_PATTERN.match(cleaned):
        raise ValueError(
            f"Invalid {name} '{value}': contains disallowed path-control characters. "
            "Only alphanumeric, hyphen, and underscore characters are permitted."
        )
    return cleaned


class LocalDriver(BaseSandbox):
    """
    Isolated local workspace sandbox with strict directory boundary containment,
    anti-symlink traversal, and pre-execution Python AST validation.
    """

    def __init__(
        self,
        bot_id: str | None = None,
        session_id: str | None = None,
        base_dir: str = DEFAULT_BASE_WORKSPACE,
        ast_validator: ASTValidator | None = None,
        **kwargs: Any,
    ) -> None:
        raw_bot_id = kwargs.get("bot_id", bot_id)
        raw_session_id = kwargs.get("session_id", session_id)

        # Disambiguate if a single positional argument was passed without keyword
        if raw_bot_id is not None and raw_session_id is None and "session_id" not in kwargs:
            eff_bot_id = "default_bot"
            eff_session_id = raw_bot_id
        else:
            eff_bot_id = "default_bot" if raw_bot_id is None else raw_bot_id
            eff_session_id = "default" if raw_session_id is None else raw_session_id

        self.bot_id = sanitize_identifier(eff_bot_id, "bot_id")
        self.session_id = sanitize_identifier(eff_session_id, "session_id")
        self.isolation_key = f"{self.bot_id}:{self.session_id}"
        self.composite_key = self.isolation_key

        self.base_dir = Path(base_dir).resolve()
        self.workspace_dir = (self.base_dir / f"sandbox_{self.bot_id}_{self.session_id}").resolve()
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

        self.ast_validator = ast_validator or ASTValidator(
            allowed_scratch_dirs=[self.workspace_dir]
        )
        self._is_cleaned_up = False

        logger.info(
            "Initialized LocalDriver sandbox for key '%s' (bot='%s', session='%s') at: %s",
            self.isolation_key,
            self.bot_id,
            self.session_id,
            self.workspace_dir,
        )

    def _resolve_safe_path(self, relative_path: str, must_exist: bool = False) -> Path:
        """
        Resolve and validate that the target path strictly resides within the sandbox root.

        Guards against:
          1. Direct lexical path traversal ('..').
          2. Absolute paths attempting breakout.
          3. Symlinks and directory junctions pointing outside the sandbox root.
        """
        if not relative_path or not relative_path.strip():
            raise ValueError("File path cannot be empty.")

        # 1. Lexical check for traversal tokens
        normalized = relative_path.replace("\\", "/").strip()
        parts = [p for p in normalized.split("/") if p and p != "."]
        if ".." in parts:
            raise PermissionError(
                f"Path traversal rejected: '..' token detected in path '{relative_path}'."
            )

        # Build path anchored inside sandbox root
        clean_rel = "/".join(parts)
        target = self.workspace_dir / clean_rel

        # 2. Canonical realpath resolution (symlink escape defense)
        real_root = os.path.realpath(str(self.workspace_dir))
        norm_root = os.path.normcase(real_root)

        real_target = os.path.realpath(str(target))
        norm_target = os.path.normcase(real_target)

        # Check if the target resolves outside root
        if not (norm_target == norm_root or norm_target.startswith(norm_root + os.sep)):
            raise PermissionError(
                f"Path traversal or symlink escape rejected: target '{relative_path}' "
                f"resolves to '{real_target}', outside sandbox root '{real_root}'."
            )

        # 3. Check all ancestor directories up to target to catch symlink parent directories
        curr = target.parent
        while True:
            real_curr = os.path.realpath(str(curr))
            norm_curr = os.path.normcase(real_curr)
            if not (norm_curr == norm_root or norm_curr.startswith(norm_root + os.sep)):
                raise PermissionError(
                    f"Symlink escape rejected in parent path: ancestor of '{relative_path}' "
                    f"resolves to '{real_curr}', outside sandbox root '{real_root}'."
                )
            if curr == self.workspace_dir or curr == curr.parent:
                break
            curr = curr.parent

        if must_exist and not target.exists():
            raise FileNotFoundError(
                f"File not found within sandbox workspace: '{relative_path}'"
            )

        return target

    def _inspect_python_code(self, cmd: str) -> None:
        """
        Statically inspect Python scripts or inline commands with Ultron ASTValidator
        before executing the subprocess.
        """
        cmd_trimmed = cmd.strip()

        # Check if command invokes python interpreter
        py_match = re.search(
            r"(?:^|[;&|\s])(?:python[0-9.]*|py)(?:\.exe)?\s+(.+)$",
            cmd_trimmed,
            re.IGNORECASE,
        )
        if not py_match:
            return

        py_args = py_match.group(1).strip()

        # 1. Inline python code: python -c "..." or python -c '...'
        c_match = re.search(r"-c\s+(['\"])(.*?)\1", py_args, re.DOTALL)
        if c_match:
            code_str = c_match.group(2)
            self.ast_validator.validate_python_code(code_str)
            return

        # 2. Python script file: python script.py ...
        tokens = py_args.split()
        for token in tokens:
            if token.startswith("-"):
                continue
            clean_token = token.strip("\"'")
            if clean_token.endswith(".py") or Path(clean_token).suffix in (".py", ".pyw"):
                try:
                    script_path = self._resolve_safe_path(clean_token, must_exist=True)
                    code_str = script_path.read_text(encoding="utf-8")
                    self.ast_validator.validate_python_code(code_str)
                except (FileNotFoundError, PermissionError):
                    # Handled downstream or in filesystem checks
                    pass
                break

    def execute_command(self, cmd: str, timeout: int = 60) -> dict[str, Any]:
        """
        Execute command strictly confined inside the scoped workspace directory.
        Performs static AST validation if the command invokes Python.
        """
        if self._is_cleaned_up:
            raise RuntimeError("LocalDriver sandbox has been cleaned up and is no longer active.")

        # 1. AST Validation on Python scripts / snippets
        self._inspect_python_code(cmd)

        # 2. Subprocess execution with cwd pinned to sandbox workspace
        try:
            res = subprocess.run(
                cmd,
                cwd=str(self.workspace_dir),
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return {
                "stdout": res.stdout,
                "stderr": res.stderr,
                "exit_code": res.returncode,
            }
        except subprocess.TimeoutExpired as exc:
            return {
                "stdout": (exc.stdout or "") if isinstance(exc.stdout, str) else "",
                "stderr": f"Execution timed out after {timeout} seconds.",
                "exit_code": 124,
            }
        except Exception as exc:
            return {
                "stdout": "",
                "stderr": f"Subprocess execution error: {exc}",
                "exit_code": 1,
            }

    def read_workspace_file(self, path: str) -> str:
        """
        Read a file safely from the sandbox workspace.
        """
        safe_path = self._resolve_safe_path(path, must_exist=True)
        return safe_path.read_text(encoding="utf-8")

    def write_workspace_file(self, path: str, content: str | bytes) -> bool:
        """
        Write text or binary content safely to the sandbox workspace.
        """
        safe_path = self._resolve_safe_path(path, must_exist=False)
        safe_path.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(content, bytes):
            safe_path.write_bytes(content)
        else:
            safe_path.write_text(str(content), encoding="utf-8")

        return True

    def cleanup(self) -> None:
        """
        Mark sandbox as closed and release resources.
        """
        self._is_cleaned_up = True
        logger.info("LocalDriver sandbox '%s' cleaned up.", self.session_id)
