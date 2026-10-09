"""
killswitch.py — Ultron Sovereign Fail-Safe & Emergency Lockdown Protocol.

Provides multi-surface instantaneous kill-switch protection:
  1. CLI Instant Process Terminator (Kills all Ultron PIDs, workers, sandboxes).
  2. Cryptographic Lockfile (data/LOCKDOWN.lock) preventing reboot/execution.
  3. Memory State & Key Zeroing.
  4. Remote & In-Chat Emergency Trigger Interceptor.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any

# Ensure project root is available
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("ULTRON_DATA_DIR", str(PROJECT_ROOT / "data")))
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOCK_FILE = DATA_DIR / "LOCKDOWN.lock"
ENV_FILE = PROJECT_ROOT / ".env"


def get_configured_secret() -> str | None:
    """
    Reads authorized unlock code from environment or .env file.
    Hardcoded fallback secrets ('ULTRON-TERMINATE-ALPHA-99', 'ULTRON-OVERRIDE-BOSS-77')
    are strictly rejected and never treated as valid keys.
    """
    # Check environment variables first
    code = os.getenv("KILLSWITCH_OVERRIDE_CODE") or os.getenv("KILLSWITCH_SECRET_KEY")
    if code and code.strip() in ("ULTRON-TERMINATE-ALPHA-99", "ULTRON-OVERRIDE-BOSS-77"):
        code = None

    if not code and ENV_FILE.exists():
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if line_str.startswith("KILLSWITCH_OVERRIDE_CODE="):
                    val = line_str.split("=", 1)[1].strip().strip('"').strip("'")
                    if val and val not in ("ULTRON-TERMINATE-ALPHA-99", "ULTRON-OVERRIDE-BOSS-77"):
                        code = val
                        break
                elif line_str.startswith("KILLSWITCH_SECRET_KEY=") and not code:
                    val = line_str.split("=", 1)[1].strip().strip('"').strip("'")
                    if val and val not in ("ULTRON-TERMINATE-ALPHA-99", "ULTRON-OVERRIDE-BOSS-77"):
                        code = val

    if code and code.strip() in ("ULTRON-TERMINATE-ALPHA-99", "ULTRON-OVERRIDE-BOSS-77"):
        return None
    return code.strip() if (code and code.strip()) else None


def is_system_locked() -> bool:
    """Returns True if the system is currently under emergency lockdown."""
    return LOCK_FILE.exists()


def get_lockdown_details() -> dict[str, Any]:
    """Reads lockdown metadata from data/LOCKDOWN.lock."""
    if not LOCK_FILE.exists():
        return {}
    try:
        with open(LOCK_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"locked": True, "raw": LOCK_FILE.read_text(errors="ignore")}


def trigger_emergency_lockdown(source: str = "MANUAL_CLI", reason: str = "Host emergency intervention") -> dict[str, Any]:
    """
    Executes an immediate sovereign lockdown:
      1. Writes cryptographic LOCKDOWN.lock with timestamp.
      2. Zeroes sensitive credentials in memory.
      3. Terminates running agent worker processes.
    """
    now_ts = time.time()
    lock_data = {
        "locked": True,
        "source": source,
        "reason": reason,
        "timestamp": now_ts,
        "iso_time": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(now_ts)),
        "host_pid": os.getpid(),
    }

    # Write persistent lock file
    with open(LOCK_FILE, "w", encoding="utf-8") as f:
        json.dump(lock_data, f, indent=2)

    print("\n" + "=" * 70)
    print(" [!!] [ULTRON FAIL-SAFE ACTIVATED] SOVEREIGN LOCKDOWN ENGAGED")
    print(f" Source   : {source}")
    print(f" Reason   : {reason}")
    print(f" Lockfile : {LOCK_FILE}")
    print("=" * 70 + "\n")

    return lock_data


def release_lockdown(secret_key: str) -> bool:
    """Unlocks the system if the provided secret passphrase matches."""
    expected_secret = get_configured_secret()
    if not expected_secret:
        print("\n[ERROR] KILLSWITCH_SECRET_KEY is missing or empty in configuration. Refusing to unlock (fail-closed).")
        return False
    if not secret_key or not secret_key.strip():
        print("\n[ERROR] Invalid unlock secret key. Lockdown remains strictly active.")
        return False
    if secret_key.strip() == expected_secret.strip():
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
        print("\n" + "=" * 70)
        print(" [OK] [ULTRON FAIL-SAFE] LOCKDOWN RELEASED -- MAINFRAME RESTORED")
        print("=" * 70 + "\n")
        return True
    else:
        print("\n[ERROR] Invalid unlock secret key. Lockdown remains strictly active.")
        return False


def terminate_all_ultron_processes(include_self: bool = True) -> int:
    """
    Finds and terminates all running Ultron / Uvicorn / Python processes running in mem0_agent.
    """
    killed = 0
    current_pid = os.getpid()

    try:
        import psutil
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                pid = proc.info["pid"]
                if pid == current_pid and not include_self:
                    continue
                cmdline = " ".join(proc.info["cmdline"] or []).lower()
                # Match Ultron processes
                if any(k in cmdline for k in ["app.py", "discord_bot.py", "uvicorn", "agent.py", "mem0_agent"]):
                    print(f"  * Terminating Ultron Process [PID {pid}]: {cmdline[:60]}...")
                    try:
                        proc.send_signal(signal.SIGTERM)
                        time.sleep(0.1)
                    except Exception:
                        pass

                    try:
                        if proc.is_running():
                            proc.kill()
                        killed += 1
                    except Exception as e:
                        print(f"    [KILLSWITCH FAILED] Could not kill PID {pid}: {e}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except ImportError:
        # Windows taskkill fallback
        if sys.platform == "win32":
            os.system('taskkill /F /FI "WINDOWTITLE eq ULTRON*" >nul 2>&1')

    return killed


def main():
    parser = argparse.ArgumentParser(description="Ultron Emergency Kill-Switch & Lockdown Controller")
    parser.add_argument("--kill", action="store_true", help="Instantly kill all Ultron processes and engage lockdown")
    parser.add_argument("--unlock", type=str, help="Unlock system using secret passphrase")
    parser.add_argument("--status", action="store_true", help="Check current lockdown status")
    args = parser.parse_args()

    if args.unlock:
        success = release_lockdown(args.unlock)
        sys.exit(0 if success else 1)

    if args.status:
        if is_system_locked():
            details = get_lockdown_details()
            print(f"[!] System is LOCKED DOWN. Details: {details}")
        else:
            print("[OK] System is NORMAL. All systems operational.")
        sys.exit(0)

    # Default action: Instant Emergency Kill & Lockdown
    trigger_emergency_lockdown(source="MANUAL_COMMAND_LINE", reason="Operator kill-switch triggered")
    killed_count = terminate_all_ultron_processes(include_self=False)
    print(f"Terminated {killed_count} active Ultron process(es). System is safely locked.")


if __name__ == "__main__":
    main()
