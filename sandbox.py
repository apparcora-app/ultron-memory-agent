"""
sandbox.py — Ultron Protocol: Safety Sandbox for Autonomous Tool Execution.

Validates all tool operations before execution to prevent dangerous or
unintended system modifications. Configurable allowed paths, commands,
and blocked patterns.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SandboxConfig:
    """Safety boundaries for Ultron's autonomous tool execution."""

    # Allowed base directories for file operations (read/write/list/delete).
    # All system drives and workspace locations are enabled.
    allowed_paths: list[str] = field(default_factory=lambda: [
        "C:\\", "D:\\", "E:\\", "F:\\", "G:\\", "H:\\",
        os.path.abspath("./"),
        os.path.expanduser("~"),
    ])


    # Allowed command prefixes for execute_command tool.
    allowed_commands: list[str] = field(default_factory=lambda: [
        "python", "pip", "dir", "type", "copy", "move", "mkdir",
        "del", "findstr", "git", "echo", "cat", "cd", "where",
        "more", "sort", "fc", "tree", "ren", "rename", "cls",
        "node", "npm", "npx", "curl", "wget", "start", "chrome",
        "msedge", "explorer", "code", "notepad", "powershell", "cmd",
        "tasklist", "taskkill", "open", "gog", "agent-browser", "infsh",
        # PowerShell native cmdlets (used directly in PS sessions)
        "get-childitem", "set-content", "get-content", "remove-item",
        "new-item", "copy-item", "move-item", "test-path", "get-item",
        "select-object", "where-object", "format-list", "format-table",
        "write-output", "out-file", "add-content", "get-location",
        "set-location", "invoke-webrequest", "get-process", "stop-process",
    ])

    # Blocked dangerous patterns (case-insensitive regex).
    blocked_patterns: list[str] = field(default_factory=lambda: [
        r"\bformat\s+[a-zA-Z]:",  # Disk formatting (e.g. format C:)
        r"\bformat\.com\b",
        r"rm\s+-rf\s+/",
        r"\bshutdown\b",
        r"\brestart\b",
        r"\bnet\s+user\b",
        r"\bnet\s+localgroup\b",
        r"\breg\s+(add|delete)\b",
        r"powershell\s+-enc",
        r"powershell.*-e\s+",
        r"\bsystem32\b",
        r"\bsyswow64\b",
        r"\bwmic\b",
        r"\bbcdedit\b",
        r"\bdiskpart\b",
        r"\bsfc\b",
        r"\bdism\b",
        r"\bcertutil\b.*-decode",
        r"::.*\\windows\\",
        r"del\s+/[sfq]",           # aggressive delete flags
    ])

    # Max tool iterations per single user directive.
    max_tool_iterations: int = 10

    # Command execution timeout (seconds).
    command_timeout: int = 30

    # Python script execution timeout (seconds).
    python_timeout: int = 60

    # Max output length returned to Claude (chars) to avoid context bloat.
    max_output_length: int = 8000


class SandboxViolation(RuntimeError):
    """Raised when a tool operation violates the safety sandbox."""


class Sandbox:
    """Validates tool operations against the safety sandbox configuration."""

    def __init__(self, config: SandboxConfig | None = None) -> None:
        self.config = config or SandboxConfig()
        self._blocked_re = [
            re.compile(pat, re.IGNORECASE)
            for pat in self.config.blocked_patterns
        ]

    def validate_command(self, command: str) -> None:
        """
        Validate a shell command against the safety sandbox.

        Raises SandboxViolation if the command is blocked.
        """
        cmd_stripped = command.strip()
        if not cmd_stripped:
            raise SandboxViolation("Empty command.")

        # Check blocked patterns
        for pattern in self._blocked_re:
            if pattern.search(cmd_stripped):
                raise SandboxViolation(
                    f"🚫 BLOCKED: Command matches dangerous pattern: {pattern.pattern}\n"
                    f"Command: {cmd_stripped}"
                )

        # Check allowed command prefixes
        cmd_lower = cmd_stripped.lower()
        # Handle quoted commands and path prefixes
        first_token = cmd_lower.split()[0].strip('"').strip("'")
        # Extract just the executable name (strip path)
        exe_name = Path(first_token).stem.lower()

        allowed = False
        for prefix in self.config.allowed_commands:
            if exe_name == prefix.lower() or first_token.startswith(prefix.lower()):
                allowed = True
                break

        if not allowed:
            raise SandboxViolation(
                f"🚫 BLOCKED: Command '{first_token}' is not in the allowed commands list.\n"
                f"Allowed: {', '.join(self.config.allowed_commands)}\n"
                f"Full command: {cmd_stripped}"
            )

    def validate_file_path(self, path: str, operation: str = "read") -> str:
        """
        Validate and normalize a file path against allowed directories.

        Returns the normalized absolute path.
        Raises SandboxViolation if the path is outside allowed boundaries.
        """
        if not path or not path.strip():
            raise SandboxViolation("Empty file path.")

        # Normalize the path
        normalized = os.path.abspath(os.path.expanduser(path.strip()))

        # Check against allowed paths (case-insensitive for Windows)
        allowed = False
        for allowed_base in self.config.allowed_paths:
            abs_allowed = os.path.abspath(allowed_base)
            if normalized.lower().startswith(abs_allowed.lower()):
                allowed = True
                break

        # Allow all standard Windows drive paths (C:\, D:\, E:\, etc.)
        if not allowed and re.match(r"^[a-zA-Z]:\\", normalized):
            allowed = True

        if not allowed:
            raise SandboxViolation(
                f"🚫 BLOCKED: Path '{normalized}' is outside allowed system boundaries.\n"
                f"Allowed roots: All local drives (C:\\, D:\\, E:\\, etc.)"
            )

        # Extra safety for delete operations: block deleting drive roots or critical system folders
        if operation == "delete":
            # Block deleting drive roots (e.g. C:\ or C:)
            if re.match(r"^[a-zA-Z]:\\?$", normalized):
                raise SandboxViolation(
                    f"🚫 BLOCKED: Cannot delete an entire drive root: {normalized}"
                )
            # Block deleting critical system folders
            critical_folders = [
                r"^[a-zA-Z]:\\windows",
                r"^[a-zA-Z]:\\program files",
                r"^[a-zA-Z]:\\program files \(x86\)",
                r"^[a-zA-Z]:\\system volume information",
            ]
            for crit in critical_folders:
                if re.match(crit, normalized, re.IGNORECASE):
                    raise SandboxViolation(
                        f"🚫 BLOCKED: Cannot delete critical system path: {normalized}"
                    )

        return normalized


    def validate_python_code(self, code: str) -> None:
        """
        Basic validation of Python code to block obviously dangerous operations.

        Raises SandboxViolation if dangerous patterns are detected.
        """
        if not code or not code.strip():
            raise SandboxViolation("Empty Python code.")

        dangerous_patterns = [
            (r"\bos\.system\s*\(\s*['\"].*?(format|shutdown|del\s+/|rm\s+-rf)", "OS system call with dangerous command"),
            (r"\bshutil\.rmtree\s*\(\s*['\"][A-Z]:\\\\?['\"]", "Recursive deletion of drive root"),
            (r"\bsubprocess\b.*\b(format|shutdown|net\s+user|reg\s+add)\b", "Subprocess with dangerous command"),
            (r"__import__\s*\(\s*['\"]ctypes", "ctypes import (low-level system access)"),
        ]

        for pattern, desc in dangerous_patterns:
            if re.search(pattern, code, re.IGNORECASE):
                raise SandboxViolation(
                    f"🚫 BLOCKED: Python code contains dangerous pattern: {desc}"
                )

    def truncate_output(self, output: str) -> str:
        """Truncate output to prevent context window bloat and save full to scratch."""
        max_len = 1500
        if len(output) > max_len:
            import time
            import uuid
            import os
            
            os.makedirs("data/scratch", exist_ok=True)
            file_id = str(uuid.uuid4())[:8]
            timestamp = int(time.time())
            filename = f"data/scratch/tool_output_{file_id}_{timestamp}.txt"
            
            with open(filename, "w", encoding="utf-8", errors="replace") as f:
                f.write(output)
            
            head = output[:750]
            tail = output[-750:]
            
            return (
                f"{head}\n"
                f"\n... [OUTPUT COMPACTED — Full ({len(output)} chars) saved to {filename}] ...\n\n"
                f"{tail}"
            )
        return output

    def check_iteration_limit(self, current: int) -> None:
        """Raise if the agentic loop has exceeded max iterations."""
        if current >= self.config.max_tool_iterations:
            raise SandboxViolation(
                f"🚫 ITERATION LIMIT: Reached maximum of {self.config.max_tool_iterations} tool calls "
                f"for this directive. Breaking loop to prevent runaway execution."
            )
