"""
environment.py — Deterministic environment isolation and secret sanitization for child subprocesses.

Prevents ambient API keys (GEMINI_API_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY),
infrastructure tokens, and passwords from leaking into child scripts executed by the agent.
"""

from __future__ import annotations

import os
import platform
from collections.abc import Mapping

# Essential OS variables required for runtime loading, dynamic linking, and temp dirs
_CORE_WINDOWS_WHITELIST = {
    "SYSTEMROOT",
    "SYSTEMDRIVE",
    "WINDIR",
    "COMSPEC",
    "PATHEXT",
    "TEMP",
    "TMP",
    "NUMBER_OF_PROCESSORS",
    "PROCESSOR_ARCHITECTURE",
    "USERPROFILE",
    "LOCALAPPDATA",
    "APPDATA",
}

_CORE_POSIX_WHITELIST = {
    "PATH",
    "HOME",
    "USER",
    "LANG",
    "LC_ALL",
    "TERM",
    "TMPDIR",
    "SHELL",
}

# Forbidden keywords in injected variables to prevent inadvertent credential leakage
_PROHIBITED_SECRET_PATTERNS = [
    "KEY",
    "TOKEN",
    "SECRET",
    "PASSWORD",
    "PASSWD",
    "AUTH",
    "CREDENTIAL",
    "APIKEY",
    "PRIVATE",
]


class SanitizedEnvironmentBuilder:
    """Constructs an unprivileged, sanitized environment dictionary for child subprocesses."""

    def __init__(
        self,
        base_path: str | None = None,
        custom_whitelist: list[str] | set[str] | None = None,
    ) -> None:
        self._is_windows = platform.system() == "Windows"
        self._whitelist = set(
            _CORE_WINDOWS_WHITELIST if self._is_windows else _CORE_POSIX_WHITELIST
        )
        if custom_whitelist:
            self._whitelist.update(custom_whitelist)

        self._default_path = base_path or (
            r"C:\Windows\system32;C:\Windows"
            if self._is_windows
            else "/usr/local/bin:/usr/bin:/bin"
        )

    def build(
        self,
        explicit_inject: Mapping[str, str] | None = None,
        isolate_python: bool = True,
    ) -> dict[str, str]:
        """Creates an isolated environment dict.

        - Strips any ambient API keys, tokens, credentials.
        - Sets PYTHONNOUSERSITE, PYTHONUNBUFFERED, and PYTHONIOENCODING if isolate_python=True.
        """
        clean_env: dict[str, str] = {}
        ambient = os.environ

        # 1. Pull strictly whitelisted OS variables from ambient environment
        for var in self._whitelist:
            if var in ambient:
                clean_env[var] = ambient[var]

        # 2. Guarantee PATH exists and is bounded
        clean_env["PATH"] = ambient.get("PATH", self._default_path)

        # 3. Python isolation flags
        if isolate_python:
            clean_env["PYTHONNOUSERSITE"] = "1"
            clean_env["PYTHONUNBUFFERED"] = "1"
            clean_env["PYTHONDONTWRITEBYTECODE"] = "1"
            clean_env["PYTHONIOENCODING"] = "utf-8"

        # 4. Explicit non-secret variables required for the specific job
        if explicit_inject:
            for k, v in explicit_inject.items():
                upper_key = k.upper()
                if any(secret_term in upper_key for secret_term in _PROHIBITED_SECRET_PATTERNS):
                    raise ValueError(
                        f"Prohibited injection of suspected secret credential into subprocess: '{k}'"
                    )
                clean_env[k] = str(v)

        return clean_env


import re as _re

_SECRET_PATTERNS = [
    _re.compile(r"sk-[a-zA-Z0-9_\-]{20,}"),
    _re.compile(r"AIza[0-9A-Za-z-_]{35}"),
    _re.compile(r"ghp_[a-zA-Z0-9]{36}"),
    _re.compile(r"glpat-[a-zA-Z0-9\-]{20}"),
]


def redact_secrets(text: str) -> str:
    """Masks secret tokens and ambient API keys in process outputs or logs."""
    if not text:
        return text
    scrubbed = str(text)
    ambient = os.environ
    for k, v in ambient.items():
        if len(v) >= 8 and any(sec in k.upper() for sec in ["KEY", "TOKEN", "SECRET", "PASS", "AUTH"]):
            scrubbed = scrubbed.replace(v, f"***REDACTED_{k}***")
    for pattern in _SECRET_PATTERNS:
        scrubbed = pattern.sub("[REDACTED_SECRET]", scrubbed)
    return scrubbed
