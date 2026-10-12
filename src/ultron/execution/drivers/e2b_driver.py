"""
e2b_driver.py — Remote Isolated Cloud MicroVM Sandbox Driver via E2B.

Provisions and orchestrates ephemeral Linux Firecracker microVMs using the E2B SDK.
Enforces an explicit '/workspace' working directory on all execution and filesystem operations.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from ultron.execution.drivers.base_sandbox import BaseSandbox

logger = logging.getLogger(__name__)

# Defensive import of E2B SDK
try:
    from e2b_code_interpreter import Sandbox as E2BSandbox  # type: ignore
except ImportError:
    try:
        from e2b import Sandbox as E2BSandbox  # type: ignore
    except ImportError:
        E2BSandbox = None


class E2BDriver(BaseSandbox):
    """
    Isolated Firecracker microVM sandbox executed in the E2B cloud runtime.
    """

    DEFAULT_WORKSPACE = "/workspace"

    def __init__(
        self,
        bot_id: str | None = None,
        session_id: str | None = None,
        api_key: str | None = None,
        cwd: str = DEFAULT_WORKSPACE,
        timeout: int = 300,
        **kwargs: Any,
    ) -> None:
        raw_bot_id = kwargs.get("bot_id", bot_id)
        raw_session_id = kwargs.get("session_id", session_id)

        if raw_bot_id is not None and raw_session_id is None and "session_id" not in kwargs:
            eff_bot_id = "default_bot"
            eff_session_id = raw_bot_id
        else:
            eff_bot_id = "default_bot" if raw_bot_id is None else raw_bot_id
            eff_session_id = "default" if raw_session_id is None else raw_session_id

        from ultron.execution.drivers.local_driver import sanitize_identifier

        self.bot_id = sanitize_identifier(eff_bot_id, "bot_id")
        self.session_id = sanitize_identifier(eff_session_id, "session_id")
        self.isolation_key = f"{self.bot_id}:{self.session_id}"
        self.composite_key = self.isolation_key

        self.api_key = api_key or os.getenv("E2B_API_KEY")
        if not self.api_key:
            raise ValueError("E2B_API_KEY must be provided or set in environment variables.")

        if E2BSandbox is None:
            raise ImportError(
                "The 'e2b_code_interpreter' or 'e2b' package is required to use E2BDriver. "
                "Install via: pip install e2b-code-interpreter or pip install e2b"
            )

        self.cwd = cwd
        self.timeout = timeout
        self._sandbox: Any = None
        self._initialize_sandbox()

    def _initialize_sandbox(self) -> None:
        """
        Initialize Firecracker microVM with explicit cwd='/workspace' and composite bot metadata tag.
        """
        logger.info(
            "Initializing E2B microVM sandbox for key '%s' (bot='%s', session='%s') with cwd='%s'...",
            self.isolation_key,
            self.bot_id,
            self.session_id,
            self.cwd,
        )

        metadata = {
            "bot_id": self.bot_id,
            "session_id": self.session_id,
            "composite_key": self.composite_key,
        }

        # Sandbox.create() with explicit cwd, timeout, and composite metadata tags
        try:
            self._sandbox = E2BSandbox.create(
                api_key=self.api_key,
                cwd=self.cwd,
                timeout=self.timeout,
                metadata=metadata,
            )
        except TypeError:
            try:
                self._sandbox = E2BSandbox.create(
                    api_key=self.api_key,
                    cwd=self.cwd,
                    timeout=self.timeout,
                )
            except TypeError:
                self._sandbox = E2BSandbox.create(
                    api_key=self.api_key,
                    timeout=self.timeout,
                )

        # Ensure explicit workspace directory exists
        try:
            if hasattr(self._sandbox, "commands") and hasattr(self._sandbox.commands, "run"):
                self._sandbox.commands.run(f"mkdir -p {self.cwd}", cwd=self.cwd)
            elif hasattr(self._sandbox, "process") and hasattr(self._sandbox.process, "start"):
                proc = self._sandbox.process.start(f"mkdir -p {self.cwd}", cwd=self.cwd)
                if hasattr(proc, "wait"):
                    proc.wait()
        except Exception as exc:
            logger.warning("Failed ensuring directory '%s' inside E2B sandbox: %s", self.cwd, exc)

    def _normalize_workspace_path(self, path: str) -> str:
        """Resolve a relative path against the designated microVM workspace directory."""
        clean = path.replace("\\", "/").strip().lstrip("/")
        return f"{self.cwd}/{clean}"

    def execute_command(self, cmd: str, timeout: int = 60) -> dict[str, Any]:
        """
        Execute command inside the E2B microVM with cwd explicitly pinned to '/workspace'.
        """
        if self._sandbox is None:
            raise RuntimeError("E2B Sandbox is closed or uninitialized.")

        try:
            # Modern e2b SDK commands interface
            if hasattr(self._sandbox, "commands"):
                res = self._sandbox.commands.run(cmd, cwd=self.cwd, timeout=timeout)
                stdout = getattr(res, "stdout", "") or ""
                stderr = getattr(res, "stderr", "") or ""
                exit_code = getattr(res, "exit_code", 0) if getattr(res, "exit_code", None) is not None else 0
                return {"stdout": stdout, "stderr": stderr, "exit_code": exit_code}

            # Legacy process interface
            if hasattr(self._sandbox, "process"):
                proc = self._sandbox.process.start(cmd, cwd=self.cwd)
                out = proc.wait()
                return {
                    "stdout": getattr(out, "stdout", "") or "",
                    "stderr": getattr(out, "stderr", "") or "",
                    "exit_code": getattr(out, "exit_code", 0) or 0,
                }

            raise RuntimeError("Unsupported E2B SDK interface: neither 'commands' nor 'process' available.")
        except Exception as exc:
            return {"stdout": "", "stderr": str(exc), "exit_code": 1}

    def read_workspace_file(self, path: str) -> str:
        """Read file from the microVM workspace."""
        if self._sandbox is None:
            raise RuntimeError("E2B Sandbox is closed or uninitialized.")

        full_path = self._normalize_workspace_path(path)
        try:
            if hasattr(self._sandbox, "files"):
                content = self._sandbox.files.read(full_path)
            elif hasattr(self._sandbox, "filesystem"):
                content = self._sandbox.filesystem.read(full_path)
            else:
                # Fallback to cat command
                res = self.execute_command(f"cat '{full_path}'")
                if res["exit_code"] != 0:
                    raise FileNotFoundError(res["stderr"])
                return res["stdout"]

            if isinstance(content, bytes):
                return content.decode("utf-8")
            return str(content)
        except Exception as exc:
            raise RuntimeError(f"Failed reading '{full_path}' from E2B sandbox: {exc}") from exc

    def write_workspace_file(self, path: str, content: str | bytes) -> bool:
        """Write file to the microVM workspace."""
        if self._sandbox is None:
            raise RuntimeError("E2B Sandbox is closed or uninitialized.")

        full_path = self._normalize_workspace_path(path)
        data = content if isinstance(content, (str, bytes)) else str(content)
        try:
            if hasattr(self._sandbox, "files"):
                self._sandbox.files.write(full_path, data)
                return True
            if hasattr(self._sandbox, "filesystem"):
                self._sandbox.filesystem.write(full_path, data)
                return True

            # Fallback: echo via command
            escaped = str(content).replace("'", "'\\''")
            res = self.execute_command(f"cat << 'EOF' > '{full_path}'\n{escaped}\nEOF")
            return res["exit_code"] == 0
        except Exception as exc:
            raise RuntimeError(f"Failed writing '{full_path}' to E2B sandbox: {exc}") from exc

    def cleanup(self) -> None:
        """Terminate the Firecracker microVM instance."""
        if self._sandbox is not None:
            try:
                if hasattr(self._sandbox, "kill"):
                    self._sandbox.kill()
                elif hasattr(self._sandbox, "close"):
                    self._sandbox.close()
            except Exception as exc:
                logger.warning("Error terminating E2B sandbox for session '%s': %s", self.session_id, exc)
            finally:
                self._sandbox = None
