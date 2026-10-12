"""
goal_dag_manager.py — Layer 5: Cognition & Reasoning Layer (Persistent Goal DAG Engine).

Manages high-level user objectives broken down into Directed Acyclic Graph (DAG) task trees.
Persists goals and task dependencies in SQLite for persistent tracking.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class GoalNode:
    goal_id: str
    title: str
    description: str
    status: str = "PENDING"  # PENDING, IN_PROGRESS, COMPLETED, FAILED
    parent_id: str | None = None
    depends_on: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    completed_at: float | None = None


class GoalDAGManager:
    """
    Goal Management (GM) and Planning Engine using Directed Acyclic Graphs (DAG).
    Implements Layer 5 of the Agentic AI Architecture.
    """

    def __init__(self, db_path: str = "./data/goals.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS goals (
                goal_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL,
                parent_id TEXT,
                depends_on TEXT,
                created_at REAL,
                completed_at REAL
            )
        """)
        conn.commit()
        conn.close()

    def create_goal_tree(self, root_title: str, root_description: str, subtasks: list[dict[str, Any]]) -> str:
        """
        Create a new high-level goal DAG tree with sub-tasks.
        """
        root_id = f"goal_{uuid.uuid4().hex[:8]}"
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Insert Root Goal
        cursor.execute(
            "INSERT INTO goals VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (root_id, root_title, root_description, "IN_PROGRESS", None, json.dumps([]), time.time(), None),
        )

        prev_id = None
        for task in subtasks:
            sub_id = f"task_{uuid.uuid4().hex[:8]}"
            title = task.get("title", "Sub-task")
            desc = task.get("description", "")
            # Sequential dependency fallback if depends_on not specified
            deps = task.get("depends_on", [prev_id] if prev_id else [])

            cursor.execute(
                "INSERT INTO goals VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (sub_id, title, desc, "PENDING", root_id, json.dumps(deps), time.time(), None),
            )
            prev_id = sub_id

        conn.commit()
        conn.close()
        return root_id

    def update_status(self, goal_id: str, status: str) -> bool:
        """Update status of a goal node."""
        status = status.upper()
        completed_at = time.time() if status in ["COMPLETED", "FAILED"] else None
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE goals SET status = ?, completed_at = ? WHERE goal_id = ?",
            (status, completed_at, goal_id),
        )
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected > 0

    def get_active_dag(self) -> list[dict[str, Any]]:
        """Return all goals formatted as a DAG structure for UI rendering."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM goals ORDER BY created_at DESC LIMIT 50")
        rows = cursor.fetchall()
        conn.close()

        goals = []
        for r in rows:
            goals.append({
                "goal_id": r["goal_id"],
                "title": r["title"],
                "description": r["description"],
                "status": r["status"],
                "parent_id": r["parent_id"],
                "depends_on": json.loads(r["depends_on"]) if r["depends_on"] else [],
                "created_at": r["created_at"],
                "completed_at": r["completed_at"],
            })
        return goals
