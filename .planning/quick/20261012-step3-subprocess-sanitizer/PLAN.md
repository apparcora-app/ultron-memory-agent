# Quick Task: Step 3 Subprocess Whitelist & Sandboxing

## Objective
Prevent credential leakage and lock down subprocess execution:
1. Implement `SanitizedEnvironmentBuilder` in `security/environment.py` with strict OS environment whitelisting, preventing ambient API keys, tokens, and passwords from leaking into child processes.
2. Wire the sanitizer into `core/tool_definitions.py` (`_handle_run_python`, `_handle_execute_command`, and `infrastructure/sandbox.py`).
3. Add a dedicated automated test suite (`tests/test_subprocess_sanitizer.py`) that empirically proves ambient secrets (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `EMAIL_PASSWORD`) are completely stripped from child process execution.
4. Verify all tests pass cleanly.
