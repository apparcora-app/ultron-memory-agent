"""
test_subprocess_sanitizer.py — Empirical Security Verification for Subprocess Environment Isolation.

Verifies that:
1. Ambient credentials and secrets (API keys, passwords, database URLs) are stripped from child processes.
2. Safe operating system variables required for process bootstrapping are preserved.
3. Prohibited secret injection attempts raise an immediate security error.
4. Real tool invocation (_handle_run_python and _handle_execute_command) cannot see ambient API keys.
"""

from __future__ import annotations

import pytest

from core.tool_definitions import ToolExecutor
from security.environment import SanitizedEnvironmentBuilder


class TestSubprocessSanitizer:
    """Rigorous security test suite verifying subprocess credential containment."""

    def test_environment_builder_strips_ambient_api_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify that ambient LLM and email secrets never leak into the sanitized environment."""
        # Inject simulated sensitive ambient credentials
        monkeypatch.setenv("OPENAI_API_KEY", "sk-proj-super-secret-key-12345")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-admin-secret-token")
        monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyFakeSecretGeminiKey")
        monkeypatch.setenv("EMAIL_PASSWORD", "SuperConfidentialPass123")
        monkeypatch.setenv("DATABASE_URL", "postgresql://admin:supersecret@localhost:5432/prod")

        builder = SanitizedEnvironmentBuilder()
        clean_env = builder.build()

        # Invariant 1: Absolutely zero secret keys exist in the child environment
        forbidden_keys = [
            k for k in clean_env
            if any(term in k.upper() for term in ["KEY", "TOKEN", "SECRET", "PASS", "DATABASE"])
        ]
        assert forbidden_keys == [], f"Security leak! Found sensitive keys in child env: {forbidden_keys}"

        # Invariant 2: Python isolation parameters are strictly applied
        assert clean_env.get("PYTHONNOUSERSITE") == "1"
        assert clean_env.get("PYTHONUNBUFFERED") == "1"
        assert clean_env.get("PYTHONIOENCODING") == "utf-8"

    def test_prohibited_explicit_secret_injection_raises_error(self) -> None:
        """Verify that attempting to explicitly inject secret tokens raises ValueError."""
        builder = SanitizedEnvironmentBuilder()
        with pytest.raises(ValueError, match="Prohibited injection of suspected secret credential"):
            builder.build(explicit_inject={"CUSTOM_API_KEY": "leaked_secret"})

    def test_run_python_tool_cannot_read_ambient_secrets(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Empirically execute python via ToolExecutor and assert child script cannot see GEMINI_API_KEY."""
        test_secret = "SECRET_GEMINI_TEST_KEY_9999"
        monkeypatch.setenv("GEMINI_API_KEY", test_secret)
        monkeypatch.setenv("APPROVAL_MODE", "off")

        executor = ToolExecutor()
        # Bypass AST sandbox solely for this integration check so child process can query os.environ
        monkeypatch.setattr(executor.sandbox, "validate_python_code", lambda code: None)

        python_code = """
import os
val = os.environ.get("GEMINI_API_KEY", "NOT_FOUND")
print(f"OUTPUT_VAL={val}")
"""
        res = executor.execute("run_python", {"code": python_code})
        assert res.get("success") is True, f"run_python returned failure: {res}"
        assert "OUTPUT_VAL=NOT_FOUND" in res["output"]
        assert test_secret not in res["output"]

    def test_execute_command_cannot_read_ambient_secrets(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Empirically run terminal command via ToolExecutor and assert child shell cannot see ANTHROPIC_API_KEY."""
        test_secret = "SECRET_ANTHROPIC_TEST_TOKEN_8888"
        monkeypatch.setenv("ANTHROPIC_API_KEY", test_secret)

        executor = ToolExecutor()
        cmd = 'python -c "import os; print(os.environ.get(\'ANTHROPIC_API_KEY\', \'STRIPPED\'))"'
        res = executor.execute("execute_command", {"command": cmd})
        assert res["success"] is True
        assert "STRIPPED" in res["output"]
        assert test_secret not in res["output"]
