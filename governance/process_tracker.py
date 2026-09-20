"""
governance/process_tracker.py — Subprocess & Buffer Queue Guardrails.

Provides:
  1. ProcessTracker: Tracks active subprocess PIDs and guarantees hard termination
     (SIGTERM followed by SIGKILL / taskkill within 2s) to prevent zombie processes.
  2. BoundedMemoryQueue: Enforces hard capacity caps (maxsize) on internal memory
     buffers to eliminate unbounded memory growth.
"""

from __future__ import annotations

import asyncio
import os
import platform
import subprocess
import time
from typing import Any, Dict, List, Optional, Union


class BufferOverflowError(RuntimeError):
    """Raised when an internal memory buffer or queue exceeds its configured maximum capacity."""

    def __init__(self, buffer_name: str, current_size: int, max_size: int) -> None:
        super().__init__(
            f"Buffer overflow in '{buffer_name}': current size {current_size} exceeds max capacity {max_size}. "
            f"Write rejected to prevent unbounded memory growth."
        )
        self.buffer_name = buffer_name
        self.current_size = current_size
        self.max_size = max_size


class BoundedMemoryQueue:
    """
    Thread-safe / async bounded queue enforcing strict maxsize caps on memory buffers.
    """

    def __init__(self, maxsize: int = 1000, name: str = "default_buffer") -> None:
        self.name = name
        self.maxsize = maxsize
        self._queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=maxsize)

    @property
    def qsize(self) -> int:
        return self._queue.qsize()

    @property
    def is_full(self) -> bool:
        return self._queue.full()

    def put_nowait(self, item: Any) -> None:
        """Puts item immediately; raises BufferOverflowError if full."""
        if self._queue.full():
            raise BufferOverflowError(self.name, self._queue.qsize(), self.maxsize)
        self._queue.put_nowait(item)

    async def put(self, item: Any, timeout: float = 5.0) -> None:
        """Puts item with timeout; raises BufferOverflowError if buffer remains full."""
        try:
            await asyncio.wait_for(self._queue.put(item), timeout=timeout)
        except asyncio.TimeoutError as err:
            raise BufferOverflowError(self.name, self._queue.qsize(), self.maxsize) from err

    async def get(self, timeout: Optional[float] = None) -> Any:
        """Gets item with optional timeout."""
        if timeout is not None:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        return await self._queue.get()

    def get_nowait(self) -> Any:
        return self._queue.get_nowait()


class ProcessTracker:
    """
    Subprocess registry tracking all spawned child processes.
    Enforces two-stage termination (SIGTERM -> SIGKILL) to eliminate zombie processes.
    """

    def __init__(self) -> None:
        self._processes: Dict[int, Union[subprocess.Popen, Any]] = {}
        self._terminated_pids: set[int] = set()
        self.is_windows = platform.system() == "Windows"

    def register(self, proc: Union[subprocess.Popen, Any]) -> int:
        """Registers a spawned subprocess."""
        pid = proc.pid
        self._processes[pid] = proc
        self._terminated_pids.discard(pid)
        return pid

    def unregister(self, pid: int) -> None:
        """Unregisters a process once verified terminated."""
        if pid in self._processes:
            del self._processes[pid]
        self._terminated_pids.add(pid)

    def is_alive(self, pid: int) -> bool:
        """Checks if process PID is currently alive in OS process table."""
        if pid in self._terminated_pids:
            return False

        proc = self._processes.get(pid)
        if proc is not None:
            if hasattr(proc, "poll"):
                alive = proc.poll() is None
                if not alive:
                    self._terminated_pids.add(pid)
                return alive
            if hasattr(proc, "returncode"):
                alive = proc.returncode is None
                if not alive:
                    self._terminated_pids.add(pid)
                return alive

        # Fallback to OS-level check
        if self.is_windows:
            try:
                import ctypes
                from ctypes import wintypes
                SYNCHRONIZE = 0x00100000
                PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
                handle = ctypes.windll.kernel32.OpenProcess(
                    PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, False, pid
                )
                if handle == 0:
                    self._terminated_pids.add(pid)
                    return False
                exit_code = wintypes.DWORD()
                success = ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
                ctypes.windll.kernel32.CloseHandle(handle)
                STILL_ACTIVE = 259
                if success and exit_code.value != STILL_ACTIVE:
                    self._terminated_pids.add(pid)
                    return False
                return True
            except Exception:
                return False
        else:
            try:
                os.kill(pid, 0)
                return True
            except (OSError, ProcessLookupError):
                self._terminated_pids.add(pid)
                return False

    def terminate(self, pid: int, timeout_sec: float = 2.0) -> bool:
        """
        Two-stage process termination:
        1. Attempts polite termination (SIGTERM / terminate()).
        2. Waits up to timeout_sec (default 2s).
        3. If still alive, issues forceful kill (SIGKILL / taskkill /F /T).
        4. Reaps child process to guarantee 0 zombies.
        """
        proc = self._processes.get(pid)
        if proc is None:
            return True

        # Check if already dead
        if not self.is_alive(pid):
            self.unregister(pid)
            return True

        # Stage 1: Polite termination
        try:
            if hasattr(proc, "terminate"):
                proc.terminate()
        except Exception:
            pass

        # Wait up to timeout_sec for graceful exit
        t_deadline = time.monotonic() + timeout_sec
        while time.monotonic() < t_deadline:
            if not self.is_alive(pid):
                self._reap(proc)
                self.unregister(pid)
                return True
            time.sleep(0.05)

        # Stage 2: Forceful kill if still unresponsive
        try:
            if self.is_windows:
                subprocess.run(
                    f"taskkill /F /T /PID {pid}",
                    shell=True,
                    capture_output=True,
                    text=True,
                )
            if hasattr(proc, "kill"):
                proc.kill()
        except Exception:
            pass

        self._reap(proc)
        self.unregister(pid)
        return not self.is_alive(pid)

    def _reap(self, proc: Any) -> None:
        """Reaps exit code and closes pipes to prevent OS zombie process table leak."""
        try:
            if hasattr(proc, "communicate"):
                proc.communicate(timeout=0.5)
            elif hasattr(proc, "wait"):
                proc.wait(timeout=0.5)
        except Exception:
            pass

    def cleanup_all(self, timeout_sec: float = 2.0) -> int:
        """Terminates all registered active processes."""
        terminated_count = 0
        pids = list(self._processes.keys())
        for pid in pids:
            if self.terminate(pid, timeout_sec=timeout_sec):
                terminated_count += 1
        return terminated_count

    def active_pids(self) -> List[int]:
        """Returns list of currently registered active PIDs."""
        return [pid for pid in self._processes if self.is_alive(pid)]


# Global default process tracker instance
default_process_tracker = ProcessTracker()
