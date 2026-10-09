"""
base_sandbox.py — Abstract Base Class for OpenBot Sandbox Execution Environments.

Defines the standard execution interface for isolated compute environments
(local scoped directories, Firecracker microVMs, containers, etc.).
"""

from __future__ import annotations

import abc
from typing import Any, Dict, Union


class BaseSandbox(abc.ABC):
    """
    Abstract contract defining sandbox execution and isolated workspace operations.
    """

    @abc.abstractmethod
    def execute_command(self, cmd: str, timeout: int = 60) -> Dict[str, Any]:
        """
        Execute a shell or script command inside the isolated sandbox.

        Args:
            cmd: Command string to execute.
            timeout: Maximum execution duration in seconds.

        Returns:
            Dict[str, Any]: Execution result dictionary with keys:
                - stdout: str
                - stderr: str
                - exit_code: int
        """
        raise NotImplementedError

    @abc.abstractmethod
    def read_workspace_file(self, path: str) -> str:
        """
        Read the contents of a file within the sandboxed workspace.

        Args:
            path: Relative path to the target file inside the workspace.

        Returns:
            str: Decoded string contents of the file.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def write_workspace_file(self, path: str, content: Union[str, bytes]) -> bool:
        """
        Write text or binary content to a file within the sandboxed workspace.

        Args:
            path: Relative path to the target file inside the workspace.
            content: String or bytes content to persist.

        Returns:
            bool: True if write succeeded.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def cleanup(self) -> None:
        """
        Release sandbox resources, terminate background processes, and perform teardown.
        """
        raise NotImplementedError

    def __enter__(self) -> BaseSandbox:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.cleanup()
