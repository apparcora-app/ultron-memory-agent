"""
concurrency/atomic_io.py — Atomic File & Artifact Persistence with Write-Replace Semantics.

Guarantees:
  1. No partially written or corrupted files during concurrent reads, crashes, or cancellations.
  2. Write-replace semantics: writes to a unique temporary file (`.tmp`) in the target directory first.
  3. Flushes and syncs to disk (`os.fsync`) before atomic renaming (`os.replace`).
  4. Both synchronous and asynchronous (non-blocking) APIs.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from pathlib import Path
from typing import Any


def atomic_write(
    target_path: str | Path,
    content: str | bytes,
    encoding: str = "utf-8",
) -> None:
    """
    Atomically writes content to target_path using write-replace semantics:
    1. Writes to temporary file in target directory.
    2. Flushes and fsyncs buffers to physical storage.
    3. Uses os.replace for an atomic filesystem replacement.
    """
    path = Path(target_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    # Temporary file MUST reside on the same filesystem/directory for atomic os.replace
    tmp_filename = f".{path.name}.{uuid.uuid4().hex[:8]}.tmp"
    tmp_path = path.parent / tmp_filename

    is_binary = isinstance(content, bytes)
    mode = "wb" if is_binary else "w"

    try:
        if is_binary:
            with open(tmp_path, mode) as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
        else:
            with open(tmp_path, mode, encoding=encoding, errors="replace") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())

        # Atomic swap with backoff retry against transient Windows filesystem locks
        max_replace_retries = 20
        for attempt in range(max_replace_retries):
            try:
                os.replace(tmp_path, path)
                break
            except PermissionError:
                if attempt == max_replace_retries - 1:
                    raise
                import time
                time.sleep(0.005 * (attempt + 1))
            except OSError as e:
                if getattr(e, "winerror", None) in (5, 32) and attempt < max_replace_retries - 1:
                    import time
                    time.sleep(0.005 * (attempt + 1))
                else:
                    raise
    except Exception:
        # Clean up temporary file on failure
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise


def atomic_write_json(
    target_path: str | Path,
    data: Any,
    indent: int = 2,
    ensure_ascii: bool = False,
) -> None:
    """Serializes data to JSON and atomically writes to target_path."""
    serialized = json.dumps(data, indent=indent, ensure_ascii=ensure_ascii)
    atomic_write(target_path, serialized, encoding="utf-8")


async def async_atomic_write(
    target_path: str | Path,
    content: str | bytes,
    encoding: str = "utf-8",
) -> None:
    """Non-blocking asynchronous version of atomic_write."""
    await asyncio.to_thread(atomic_write, target_path, content, encoding)


async def async_atomic_write_json(
    target_path: str | Path,
    data: Any,
    indent: int = 2,
    ensure_ascii: bool = False,
) -> None:
    """Non-blocking asynchronous version of atomic_write_json."""
    serialized = json.dumps(data, indent=indent, ensure_ascii=ensure_ascii)
    await asyncio.to_thread(atomic_write, target_path, serialized, "utf-8")


def safe_read(target_path: str | Path, encoding: str = "utf-8") -> str:
    """Reads file content safely, handling transient Windows filesystem sharing races."""
    path = Path(target_path).resolve()
    max_retries = 20
    for attempt in range(max_retries):
        try:
            with open(path, encoding=encoding, errors="replace") as f:
                return f.read()
        except (PermissionError, FileNotFoundError):
            if attempt == max_retries - 1:
                raise
            import time
            time.sleep(0.005 * (attempt + 1))
    raise RuntimeError(f"Failed to safely read file '{path}' after {max_retries} attempts.")


def safe_read_json(target_path: str | Path) -> Any:
    """Reads and parses JSON safely from target_path."""
    raw = safe_read(target_path, encoding="utf-8")
    return json.loads(raw)
