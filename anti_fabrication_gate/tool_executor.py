"""
tool_executor.py — The ONLY call-site for ledger.record().

This module wraps all real subprocess / file-operation calls.
It is the SOLE place in the codebase that is allowed to call
ledger.record(). The gate enforces this structurally: no other
module imports record(), and grepping the codebase confirms
the single call-site.

All other modules receive a read-only reference to the ledger
(they may call ledger.get() but not ledger.record()).
"""

from __future__ import annotations

import subprocess
import uuid
from datetime import datetime, timezone
from typing import Optional

from evidence_ledger import EvidenceLedger, LedgerEntry


# ---------------------------------------------------------------------------
# Public executor
# ---------------------------------------------------------------------------

def execute_command(
    cmd: list[str] | str,
    ledger: EvidenceLedger,
    tool_call_id: Optional[str] = None,
    *,
    shell: bool = False,
    timeout: int = 30,
    cwd: Optional[str] = None,
) -> LedgerEntry:
    """
    Run a subprocess, record the result in the ledger, and return the entry.

    This is the ONLY function that calls ledger.record(). It does so
    immediately after the real subprocess returns — not from any
    synthesizer, formatter, or critic.

    Parameters
    ----------
    cmd           : command as list (preferred) or shell string
    ledger        : the current-turn EvidenceLedger
    tool_call_id  : stable ID for this call; auto-generated if omitted
    shell         : passed directly to subprocess.run
    timeout       : seconds before TimeoutExpired is raised
    cwd           : working directory for the subprocess

    Returns
    -------
    The immutable LedgerEntry that was recorded.
    """
    if tool_call_id is None:
        tool_call_id = str(uuid.uuid4())

    tool_name = (
        cmd[0] if isinstance(cmd, list) else cmd.split()[0]
    )

    try:
        result = subprocess.run(
            cmd,
            shell=shell,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
        raw_stdout = result.stdout
        raw_stderr = result.stderr
        exit_code  = result.returncode
    except subprocess.TimeoutExpired as exc:
        raw_stdout = exc.stdout or ""
        raw_stderr = f"TimeoutExpired after {timeout}s"
        exit_code  = -1
    except Exception as exc:          # noqa: BLE001
        raw_stdout = ""
        raw_stderr = f"ExecutionError: {exc}"
        exit_code  = -2

    # ---------------------------------------------------------------
    # THE ONLY CALL TO ledger.record() IN THE ENTIRE CODEBASE
    # ---------------------------------------------------------------
    entry = ledger.record(
        tool_name    = tool_name,
        tool_call_id = tool_call_id,
        raw_stdout   = raw_stdout,
        raw_stderr   = raw_stderr,
        exit_code    = exit_code,
        timestamp    = datetime.now(tz=timezone.utc),
    )
    # ---------------------------------------------------------------

    return entry
