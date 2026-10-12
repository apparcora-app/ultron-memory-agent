"""
governance/db_manager.py — Unified SQLite Database Connection & Pragma Manager.

Provides:
  1. High-concurrency SQLite connection factory enforcing Write-Ahead Logging (WAL),
     NORMAL synchrony, and 5000ms busy timeouts.
  2. Safe context manager ensuring connections are 100% closed, eliminating Windows file locks.
  3. Online atomic database snapshot and backup routines without stopping agent operations.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone

from ultron.core.log_config import get_logger


class DatabaseManager:
    """
    Centralized SQLite database manager ensuring optimal concurrency pragmas,
    thread-safe connections, and atomic backup capabilities across all local stores.
    """

    def __init__(self, default_busy_timeout_ms: int = 5000) -> None:
        self.default_busy_timeout_ms = default_busy_timeout_ms
        self._lock = threading.Lock()

    @contextmanager
    def connect(
        self,
        db_path: str,
        enable_wal: bool = True,
        busy_timeout_ms: int | None = None,
    ) -> Iterator[sqlite3.Connection]:
        """
        Context-managed SQLite connection ensuring proper configuration and deterministic cleanup.
        """
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        timeout_ms = busy_timeout_ms or self.default_busy_timeout_ms

        conn = sqlite3.connect(
            db_path,
            timeout=float(timeout_ms) / 1000.0,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row

        try:
            # Apply production pragmas
            if enable_wal:
                conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute(f"PRAGMA busy_timeout = {timeout_ms};")
            conn.execute("PRAGMA foreign_keys = ON;")

            yield conn
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def backup_database(
        self,
        source_db_path: str,
        destination_path: str | None = None,
        backup_dir: str | None = None,
    ) -> str:
        """
        Performs an online, consistent atomic backup of a SQLite database
        using the native SQLite online backup API without locking readers.
        """
        if not os.path.isfile(source_db_path):
            raise FileNotFoundError(f"Source database not found: {source_db_path}")

        if destination_path is None:
            db_filename = os.path.basename(source_db_path)
            target_dir = backup_dir or "./data/backups"
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            destination_path = os.path.join(target_dir, f"{timestamp}_{db_filename}")

        os.makedirs(os.path.dirname(os.path.abspath(destination_path)), exist_ok=True)

        with self.connect(source_db_path) as src_conn:
            with sqlite3.connect(destination_path) as dst_conn:
                src_conn.backup(dst_conn)

        return destination_path

    def backup_all(
        self,
        data_dir: str = "./data",
        backup_dir: str = "./data/backups",
    ) -> dict[str, str]:
        """
        Discovers all active SQLite databases in data_dir and creates consistent backups.
        Returns a mapping of database name -> backup file path.
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        target_dir = os.path.join(backup_dir, f"snapshot_{timestamp}")
        os.makedirs(target_dir, exist_ok=True)

        backups: dict[str, str] = {}
        if not os.path.isdir(data_dir):
            return backups

        for entry in os.listdir(data_dir):
            full_path = os.path.join(data_dir, entry)
            if os.path.isfile(full_path) and (entry.endswith(".sqlite3") or entry.endswith(".db")):
                dest_path = os.path.join(target_dir, entry)
                try:
                    self.backup_database(full_path, dest_path)
                    backups[entry] = dest_path
                except Exception as e:
                    backups[entry] = f"ERROR: {e}"

        return backups


# Global default database manager
default_db_manager = DatabaseManager()

_log = get_logger('db_manager')
