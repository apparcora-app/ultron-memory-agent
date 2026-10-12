"""
guardrails/ast_sandbox.py — AST-Level Code Execution Sandboxing.

Uses Python's native `ast` module to statically inspect dynamic code before runtime.
Enforces:
  1. Whitelist of safe standard libraries (math, json, datetime, re, etc.).
  2. Hard-blocking of dangerous constructs: eval, exec, __import__, os.system, subprocess, socket,
     and unauthorized file writes outside sandboxed scratchpads.
  3. Fail-fast security violation reporting with line number, node type, and violation reason.
"""

from __future__ import annotations

import ast
import os
from collections.abc import Sequence
from pathlib import Path


class ASTSecurityViolation(RuntimeError):
    """Raised when Python code violates static AST safety rules."""

    def __init__(
        self,
        violation_type: str,
        reason: str,
        lineno: int | None = None,
        col_offset: int | None = None,
        node_repr: str | None = None,
    ) -> None:
        location = f"line {lineno}:{col_offset}" if lineno is not None else "unknown location"
        super().__init__(f"🚫 AST SECURITY VIOLATION [{violation_type}] at {location}: {reason}")
        self.violation_type = violation_type
        self.reason = reason
        self.lineno = lineno
        self.col_offset = col_offset
        self.node_repr = node_repr


# Whitelist of permissible standard libraries and numerical packages
DEFAULT_SAFE_MODULES: frozenset[str] = frozenset({
    "math",
    "cmath",
    "json",
    "datetime",
    "time",
    "re",
    "random",
    "collections",
    "itertools",
    "functools",
    "string",
    "typing",
    "csv",
    "decimal",
    "fractions",
    "statistics",
    "hashlib",
    "base64",
    "uuid",
    "copy",
    "heapq",
    "bisect",
    "pandas",
    "numpy",
    "scipy",
    "openpyxl",
    "tabulate",
    "pydantic",
    "langchain",
    "langchain_core",
    "langgraph",
    "crewai",
    "crewai_tools",
    "openai",
    "langchain_openai",
    "pathlib",
    "litellm",
    "dotenv",
    "sqlite3",
    "io",
    "dataclasses",
    "logging",
    "contextlib",
    "abc",
    "enum",
})

# Hard-blocked dangerous module roots
DANGEROUS_MODULES: frozenset[str] = frozenset({
    "os",
    "sys",
    "subprocess",
    "socket",
    "pty",
    "shutil",
    "importlib",
    "ctypes",
    "builtins",
    "posix",
    "nt",
    "threading",
    "multiprocessing",
    "asyncio",
    "signal",
    "pickle",
    "marshal",
    "shelve",
    "tempfile",
    "http",
    "urllib",
    "requests",
    "aiohttp",
    "paramiko",
    "fabric",
    "winreg",
    "_winapi",
})

# Prohibited built-in callable identifiers
PROHIBITED_CALLS: frozenset[str] = frozenset({
    "eval",
    "exec",
    "compile",
    "__import__",
    "globals",
    "locals",
    "breakpoint",
    "memoryview",
})

# Prohibited dunder attributes used in sandbox escapes
PROHIBITED_ATTRIBUTES: frozenset[str] = frozenset({
    "__subclasses__",
    "__bases__",
    "__globals__",
    "__code__",
    "__builtins__",
    "__class__",
    "__mro__",
    "__dict__",
})


class ASTValidator:
    """
    Static code analyzer using Python's native AST parser.
    Intercepts and blocks security hazards prior to code execution.
    """

    def __init__(
        self,
        safe_modules: Sequence[str] | None = None,
        allowed_scratch_dirs: Sequence[str | Path] | None = None,
    ) -> None:
        self.safe_modules = frozenset(safe_modules) if safe_modules is not None else DEFAULT_SAFE_MODULES
        self.allowed_scratch_dirs = [
            os.path.abspath(str(p)).lower()
            for p in (allowed_scratch_dirs or ["data/scratch", "./data/scratch", "scratch", ".", "./", os.getcwd()])
        ]

    def validate_python_code(self, code: str) -> None:
        """
        Parses and inspects Python source code.
        Raises ASTSecurityViolation on forbidden imports, dangerous calls, or unauthorized writes.
        """
        if not code or not code.strip():
            raise ASTSecurityViolation("empty_code", "Code snippet is empty.", lineno=1)

        try:
            tree = ast.parse(code)
        except SyntaxError as err:
            raise ASTSecurityViolation(
                violation_type="syntax_error",
                reason=f"Code fails to parse into valid Python AST: {err.msg}",
                lineno=err.lineno,
                col_offset=err.offset,
            ) from err

        for node in ast.walk(tree):
            # 1. Inspect direct imports (e.g., import os, import subprocess)
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_mod = alias.name.split(".")[0].lower()
                    if root_mod in DANGEROUS_MODULES or (root_mod not in self.safe_modules):
                        raise ASTSecurityViolation(
                            violation_type="forbidden_import",
                            reason=f"Import of module '{alias.name}' is strictly forbidden by sandbox policy.",
                            lineno=node.lineno,
                            col_offset=node.col_offset,
                            node_repr=ast.unparse(node) if hasattr(ast, "unparse") else alias.name,
                        )

            # 2. Inspect from-imports (e.g., from subprocess import Popen)
            elif isinstance(node, ast.ImportFrom):
                mod = (node.module or "").split(".")[0].lower()
                if mod in DANGEROUS_MODULES or (mod and mod not in self.safe_modules):
                    raise ASTSecurityViolation(
                        violation_type="forbidden_import_from",
                        reason=f"Import from module '{node.module}' is strictly forbidden by sandbox policy.",
                        lineno=node.lineno,
                        col_offset=node.col_offset,
                        node_repr=ast.unparse(node) if hasattr(ast, "unparse") else str(node.module),
                    )

            # 3. Inspect Function and Method Calls
            elif isinstance(node, ast.Call):
                self._check_call_node(node)

            # 4. Inspect Attribute Access (block __globals__, __subclasses__, os.system, etc.)
            elif isinstance(node, ast.Attribute):
                if node.attr in PROHIBITED_ATTRIBUTES:
                    raise ASTSecurityViolation(
                        violation_type="forbidden_attribute_access",
                        reason=f"Access to introspection dunder '{node.attr}' is blocked to prevent sandbox breakout.",
                        lineno=node.lineno,
                        col_offset=node.col_offset,
                        node_repr=node.attr,
                    )

    def _check_call_node(self, node: ast.Call) -> None:
        """Inspects call expressions for eval/exec or dangerous module calls."""
        # A. Direct call by name: eval(...), exec(...)
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in PROHIBITED_CALLS:
                raise ASTSecurityViolation(
                    violation_type="prohibited_builtin_call",
                    reason=f"Calling '{func_name}' is strictly prohibited.",
                    lineno=node.lineno,
                    col_offset=node.col_offset,
                    node_repr=func_name,
                )

            # Check open() calls for write access outside scratchpads
            if func_name == "open":
                self._check_open_call(node)

        # B. Method / Attribute calls: os.system(...), subprocess.Popen(...), socket.socket(...)
        elif isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr
            # Detect calls on suspicious names or attributes
            if attr_name in {"system", "popen", "spawn", "fork", "execv", "execl"}:
                raise ASTSecurityViolation(
                    violation_type="system_execution_call",
                    reason=f"Direct system execution method '{attr_name}' is blocked.",
                    lineno=node.lineno,
                    col_offset=node.col_offset,
                    node_repr=attr_name,
                )
            if attr_name in {"bind", "listen", "accept"}:
                raise ASTSecurityViolation(
                    violation_type="socket_operation",
                    reason=f"Socket network operation '{attr_name}' is blocked.",
                    lineno=node.lineno,
                    col_offset=node.col_offset,
                    node_repr=attr_name,
                )

    def _check_open_call(self, node: ast.Call) -> None:
        """Verifies that open() operations only write within allowed scratchpad paths."""
        is_write = False
        # Check positional mode argument (index 1)
        if len(node.args) >= 2:
            mode_arg = node.args[1]
            if isinstance(mode_arg, ast.Constant) and isinstance(mode_arg.value, str):
                if any(m in mode_arg.value for m in ("w", "a", "+", "x")):
                    is_write = True

        # Check keyword mode argument
        for kw in node.keywords:
            if kw.arg == "mode" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                if any(m in kw.value.value for m in ("w", "a", "+", "x")):
                    is_write = True

        if is_write:
            # File path must be a constant string inside allowed scratchpad
            if not node.args:
                raise ASTSecurityViolation(
                    violation_type="unauthorized_file_write",
                    reason="File write open() called without target path.",
                    lineno=node.lineno,
                    col_offset=node.col_offset,
                )
            path_arg = node.args[0]
            if isinstance(path_arg, ast.Constant) and isinstance(path_arg.value, str):
                target_path = os.path.abspath(path_arg.value).lower()
                allowed = False
                for scratch_dir in self.allowed_scratch_dirs:
                    if target_path.startswith(scratch_dir):
                        allowed = True
                        break
                # Also allow writing inside system temp directory
                import tempfile
                temp_dir = os.path.abspath(tempfile.gettempdir()).lower()
                if target_path.startswith(temp_dir):
                    allowed = True

                if not allowed:
                    raise ASTSecurityViolation(
                        violation_type="unauthorized_file_write",
                        reason=(
                            f"Unauthorized write to '{path_arg.value}'. "
                            f"Writes are restricted strictly to sandboxed scratchpads ({', '.join(self.allowed_scratch_dirs)})."
                        ),
                        lineno=node.lineno,
                        col_offset=node.col_offset,
                        node_repr=path_arg.value,
                    )


    def is_safe(self, code: str) -> tuple[bool, str | None]:
        """Convenience method returning (is_safe, error_message)."""
        try:
            self.validate_python_code(code)
            return True, None
        except ASTSecurityViolation as err:
            return False, str(err)
