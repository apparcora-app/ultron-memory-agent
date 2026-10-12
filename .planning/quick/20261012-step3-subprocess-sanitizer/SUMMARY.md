# Quick Task Summary: Step 3 Subprocess Whitelist & Sandboxing

## Objective
Prevent ambient credential and secret leakage into child processes spawned by Ultron tools (`run_python` and `execute_command`).

## Implementation Details
1. **`security/environment.py`**:
   - Implemented `SanitizedEnvironmentBuilder` using strict whitelist filtering.
   - Retains essential system bootstrapping variables (`SYSTEMROOT`, `SYSTEMDRIVE`, `WINDIR`, `PATH`, `PATHEXT`, `COMSPEC`, `TEMP`, `TMP`, `USERPROFILE`, `HOMEDRIVE`, `HOMEPATH`).
   - Strictly enforces Python isolation environment flags: `PYTHONNOUSERSITE=1`, `PYTHONUNBUFFERED=1`, `PYTHONIOENCODING=utf-8`.
   - Prohibits any variables matching credential heuristics (`KEY`, `TOKEN`, `SECRET`, `PASS`, `AUTH`, `DATABASE`, etc.), throwing a `ValueError` on attempted explicit injection.
2. **`core/tool_definitions.py`**:
   - Integrated `SanitizedEnvironmentBuilder` in both `_handle_run_python` and `_handle_execute_command`, guaranteeing child scripts and shell processes receive sanitized environments.
3. **`tests/test_subprocess_sanitizer.py`**:
   - Added unit and live subprocess test coverage verifying:
     - Ambient API keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, etc.) are stripped.
     - Prohibited explicit secret injections raise an immediate security error.
     - Live execution via `run_python` cannot read ambient credentials.
     - Live execution via `execute_command` cannot read ambient credentials.

## Empirical Verification
- Ruff lint check: `ruff check security/environment.py tests/test_subprocess_sanitizer.py` -> Passed with 0 errors.
- Test execution: `pytest tests/test_subprocess_sanitizer.py -v` -> 4 passed in 2.51s.
