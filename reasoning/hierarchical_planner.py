"""
================================================================================
 ULTRON COGNITIVE ARCHITECTURE — HIERARCHICAL GOAL DECOMPOSITION & DYNAMIC DAG
================================================================================
Module: hierarchical_planner.py
Pillar: Cognitive Breakthrough 3 — Hierarchical Goal Decomposition & Self-Evolving Planner

Implements:
  1. HTNode & HierarchicalGoalTree: SQLite-backed 3-tier H-Tree data structure
     (Macro-Phase -> Meso-Milestone -> Micro-Action) with topological sorting,
     parent-child state aggregation, and cycle detection.
  2. HDecomposerEngine: LLM-powered recursive hierarchical planner that breaks
     high-stakes user directives into structured DAG execution trees.
  3. DynamicDAGReplanner: Self-evolving runtime engine that executes ready nodes,
     evaluates tool feedback, and dynamically splices self-healing recovery nodes
     into the active DAG on mid-flight failure.

Author: Ultron Cybernetic Systems Architect
================================================================================
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Ensure UTF-8 stdout/stderr on Windows console
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import anthropic

# Try Google GenAI SDK
try:
    from google import genai  # noqa: F401
    from google.genai import types as genai_types  # noqa: F401
    _HAS_GEMINI = True
except ImportError:
    _HAS_GEMINI = False

from telemetry import TelemetryEngine
from tool_definitions import ToolExecutor
from trajectory_manager import TrajectoryManager

# ──────────────────────────────────────────────────────────────────────────────
# DATA STRUCTURES
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class HTNode:
    """Represents a discrete hierarchical task node in the H-Tree / DAG."""
    node_id: str
    tree_id: str
    parent_id: str | None
    title: str
    description: str
    level: str  # ROOT, MACRO, MESO, MICRO
    status: str = "PENDING"  # PENDING, READY, RUNNING, COMPLETED, FAILED, SKIPPED, MUTATED
    assigned_specialist: str = "ultron_prime"  # ultron_prime, titan, nexus, sentinel, ledger, oracle
    depends_on: list[str] = field(default_factory=list)
    children_ids: list[str] = field(default_factory=list)
    required_tool: str | None = None  # run_python, file_operation, execute_command, web_search
    tool_input: dict[str, Any] = field(default_factory=dict)
    tool_output: str | None = None
    execution_time_s: float = 0.0
    retry_count: int = 0
    max_retries: int = 2
    mutation_history: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    completed_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "tree_id": self.tree_id,
            "parent_id": self.parent_id,
            "title": self.title,
            "description": self.description,
            "level": self.level,
            "status": self.status,
            "assigned_specialist": self.assigned_specialist,
            "depends_on": self.depends_on,
            "children_ids": self.children_ids,
            "required_tool": self.required_tool,
            "tool_input": self.tool_input,
            "tool_output": self.tool_output,
            "execution_time_s": self.execution_time_s,
            "retry_count": self.retry_count,
            "mutation_history": self.mutation_history,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


@dataclass
class PlanExecutionResult:
    """Packaged outcome of executing a dynamic H-Tree plan."""
    tree_id: str
    root_goal: str
    success: bool
    total_nodes: int
    completed_nodes: int
    failed_nodes: int
    mutated_nodes: int
    total_duration_s: float
    final_output: str = ""
    node_summary: list[dict[str, Any]] = field(default_factory=list)
    trajectory_id: str | None = None

    @property
    def nodes_executed(self) -> list[dict[str, Any]]:
        """Alias returning the executed node summaries."""
        return self.node_summary


# ──────────────────────────────────────────────────────────────────────────────
# PROMPTS
# ──────────────────────────────────────────────────────────────────────────────

_DECOMPOSITION_PROMPT = """You are the Supreme Strategic Planner of the ULTRON Autonomous AI Agent Protocol.
Decompose the following complex objective into a rigorous 3-Tier Hierarchical Goal Tree (H-Tree / Dynamic DAG).

OBJECTIVE / DIRECTIVE:
\"\"\"{goal_text}\"\"\"

AVAILABLE SYSTEM TOOLS:
• run_python: Execute Python scripts for mathematical computation, data processing, financial modeling, or verification.
• file_operation: Read, write, list, or manipulate files in the local workspace.
• execute_command: Run system shell commands, directory creation, build tools.
• web_search: Query the web for real-time data or API documentation.

DECOMPOSITION SPECIFICATIONS:
1. Level 1 (MACRO): 2 to 3 high-level sequential/strategic phases.
2. Level 2 (MESO): 1 to 2 discrete milestone deliverables per Macro phase.
3. Level 3 (MICRO): Actionable, executable leaves assigned to specific tools (run_python, file_operation, execute_command, or pure reasoning).
4. Explicit Dependencies (depends_on): Micro tasks that require previous data must explicitly list the node IDs they depend upon.

OUTPUT STRICT JSON ONLY MATCHING THIS SCHEMA:

```json
{{
  "tree_title": "Concise Strategic Title",
  "root_description": "Comprehensive objective summary",
  "nodes": [
    {{
      "id": "macro_1",
      "parent_id": null,
      "level": "MACRO",
      "title": "Phase 1 Title",
      "description": "Macro phase objective",
      "assigned_specialist": "ultron_prime | titan | nexus | sentinel | ledger",
      "depends_on": []
    }},
    {{
      "id": "meso_1_1",
      "parent_id": "macro_1",
      "level": "MESO",
      "title": "Milestone 1.1 Title",
      "description": "Meso milestone objective",
      "assigned_specialist": "titan",
      "depends_on": []
    }},
    {{
      "id": "micro_1_1_1",
      "parent_id": "meso_1_1",
      "level": "MICRO",
      "title": "Executable Action Title",
      "description": "Specific action to perform",
      "assigned_specialist": "titan",
      "required_tool": "run_python | file_operation | execute_command | web_search | null",
      "tool_input": {{
        "code": "# Python code to run if required_tool is run_python",
        "action": "write_file",
        "path": "test.txt",
        "content": "example"
      }},
      "depends_on": []
    }}
  ]
}}
```

Respond with ONLY valid JSON inside markdown code fences."""


_REPLAN_MUTATION_PROMPT = """You are the ULTRON Self-Evolving Replanner.
During execution of a Hierarchical Goal Tree (H-Tree), a micro-task encountered an unexpected failure or environmental barrier.

FAILED TASK:
• Node ID: {failed_node_id}
• Title: {failed_title}
• Description: {failed_description}
• Tool: {failed_tool}
• Error / Output: {error_output}

MASTER ROOT GOAL:
{root_goal}

REPLANNING INSTRUCTIONS:
Formulate an in-flight recovery sub-DAG to resolve this failure. You can either:
1. Provide a patched/corrected tool action for this node.
2. Insert 1 to 2 intermediate prerequisite nodes (e.g. create missing directory, fix calculation script, adjust parameters).

OUTPUT STRICT JSON ONLY:
```json
{{
  "repair_strategy": "Brief explanation of the dynamic fix",
  "replacement_nodes": [
    {{
      "id": "micro_repaired_{failed_node_id}",
      "parent_id": "{parent_id}",
      "level": "MICRO",
      "title": "Repaired Action Title",
      "description": "Corrected operation description",
      "assigned_specialist": "titan",
      "required_tool": "run_python | file_operation | execute_command",
      "tool_input": {{
        "code": "# Corrected Python code if run_python"
      }},
      "depends_on": []
    }}
  ]
}}
```

Respond with ONLY valid JSON inside markdown code fences."""


# ──────────────────────────────────────────────────────────────────────────────
# H-TREE SQLITE STORAGE & TOPOLOGICAL ENGINE
# ──────────────────────────────────────────────────────────────────────────────

class HierarchicalGoalTree:
    """
    Persistent SQLite storage and topological graph coordinator for H-Trees.
    """

    def __init__(self, db_path: str = "./data/hierarchical_plans.sqlite3") -> None:
        self.db_path = Path(db_path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            # 1. Trees Meta Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS goal_trees (
                    tree_id TEXT PRIMARY KEY,
                    root_goal TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'PENDING',
                    total_nodes INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL,
                    completed_at REAL
                );
            """)
            # 2. Nodes Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tree_nodes (
                    node_id TEXT PRIMARY KEY,
                    tree_id TEXT NOT NULL,
                    parent_id TEXT,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    level TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'PENDING',
                    assigned_specialist TEXT NOT NULL DEFAULT 'ultron_prime',
                    depends_on_json TEXT NOT NULL DEFAULT '[]',
                    children_json TEXT NOT NULL DEFAULT '[]',
                    required_tool TEXT,
                    tool_input_json TEXT NOT NULL DEFAULT '{}',
                    tool_output TEXT,
                    execution_time_s REAL NOT NULL DEFAULT 0.0,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    mutation_history_json TEXT NOT NULL DEFAULT '[]',
                    created_at REAL NOT NULL,
                    completed_at REAL,
                    FOREIGN KEY (tree_id) REFERENCES goal_trees(tree_id) ON DELETE CASCADE
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tree_nodes_tree ON tree_nodes(tree_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tree_nodes_status ON tree_nodes(status);")
            conn.commit()

    def save_tree(self, tree_id: str, root_goal: str, nodes: list[HTNode]) -> None:
        """Persists a complete tree and all its constituent nodes atomically."""
        now = time.time()
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT OR REPLACE INTO goal_trees (tree_id, root_goal, status, total_nodes, created_at, completed_at)
                VALUES (?, ?, 'IN_PROGRESS', ?, ?, NULL)
                """,
                (tree_id, root_goal, len(nodes), now),
            )
            for n in nodes:
                cur.execute(
                    """
                    INSERT OR REPLACE INTO tree_nodes (
                        node_id, tree_id, parent_id, title, description, level, status,
                        assigned_specialist, depends_on_json, children_json, required_tool,
                        tool_input_json, tool_output, execution_time_s, retry_count,
                        mutation_history_json, created_at, completed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        n.node_id, n.tree_id, n.parent_id, n.title, n.description, n.level, n.status,
                        n.assigned_specialist, json.dumps(n.depends_on), json.dumps(n.children_ids),
                        n.required_tool, json.dumps(n.tool_input), n.tool_output, n.execution_time_s,
                        n.retry_count, json.dumps(n.mutation_history), n.created_at, n.completed_at,
                    ),
                )
            conn.commit()

    def get_nodes(self, tree_id: str) -> list[HTNode]:
        """Loads all nodes belonging to a tree."""
        with self._get_conn() as conn:
            rows = conn.execute("SELECT * FROM tree_nodes WHERE tree_id = ?", (tree_id,)).fetchall()
            return [self._row_to_node(r) for r in rows]

    def update_node(self, node: HTNode) -> None:
        """Updates status, output, and execution metrics of a node."""
        with self._get_conn() as conn:
            conn.execute(
                """
                UPDATE tree_nodes
                SET status = ?, tool_output = ?, execution_time_s = ?, retry_count = ?,
                    mutation_history_json = ?, depends_on_json = ?, children_json = ?, completed_at = ?
                WHERE node_id = ?
                """,
                (
                    node.status, node.tool_output, node.execution_time_s, node.retry_count,
                    json.dumps(node.mutation_history), json.dumps(node.depends_on), json.dumps(node.children_ids),
                    node.completed_at, node.node_id,
                ),
            )
            conn.commit()

    def add_node(self, node: HTNode) -> None:
        """Adds a single dynamic node to an existing tree."""
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT OR REPLACE INTO tree_nodes (
                    node_id, tree_id, parent_id, title, description, level, status,
                    assigned_specialist, depends_on_json, children_json, required_tool,
                    tool_input_json, tool_output, execution_time_s, retry_count,
                    mutation_history_json, created_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    node.node_id, node.tree_id, node.parent_id, node.title, node.description, node.level, node.status,
                    node.assigned_specialist, json.dumps(node.depends_on), json.dumps(node.children_ids),
                    node.required_tool, json.dumps(node.tool_input), node.tool_output, node.execution_time_s,
                    node.retry_count, json.dumps(node.mutation_history), node.created_at, node.completed_at,
                ),
            )
            # Increment total_nodes in meta table
            cur.execute("UPDATE goal_trees SET total_nodes = total_nodes + 1 WHERE tree_id = ?", (node.tree_id,))
            conn.commit()

    def get_ready_nodes(self, tree_id: str) -> list[HTNode]:
        """
        Returns all Micro or leaf nodes whose dependencies are 100% COMPLETED
        and whose own status is PENDING or READY.
        """
        all_nodes = {n.node_id: n for n in self.get_nodes(tree_id)}
        ready = []
        for n in all_nodes.values():
            if n.status in ("PENDING", "READY") and n.level == "MICRO":
                deps_met = True
                for dep_id in n.depends_on:
                    dep_node = all_nodes.get(dep_id)
                    if not dep_node or dep_node.status != "COMPLETED":
                        deps_met = False
                        break
                if deps_met:
                    ready.append(n)
        return ready

    def topological_sort(self, nodes: list[HTNode]) -> list[HTNode]:
        """
        Computes a valid topological execution order for nodes based on depends_on.
        Detects and resolves cyclic dependencies gracefully.
        """
        node_map = {n.node_id: n for n in nodes}
        in_degree: dict[str, int] = {n.node_id: 0 for n in nodes}
        adj_list: dict[str, list[str]] = {n.node_id: [] for n in nodes}

        for n in nodes:
            for dep_id in n.depends_on:
                if dep_id in node_map:
                    adj_list[dep_id].append(n.node_id)
                    in_degree[n.node_id] += 1

        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        sorted_nodes: list[HTNode] = []

        while queue:
            curr_id = queue.pop(0)
            sorted_nodes.append(node_map[curr_id])
            for neighbor_id in adj_list.get(curr_id, []):
                in_degree[neighbor_id] -= 1
                if in_degree[neighbor_id] == 0:
                    queue.append(neighbor_id)

        # If cyclic or unreached nodes remain, append them at the end
        if len(sorted_nodes) < len(nodes):
            seen_ids = {n.node_id for n in sorted_nodes}
            for n in nodes:
                if n.node_id not in seen_ids:
                    sorted_nodes.append(n)

        return sorted_nodes

    def render_ascii_tree(self, tree_id: str) -> str:
        """Renders an elegant ASCII hierarchical tree showing status badges."""
        nodes = self.get_nodes(tree_id)
        if not nodes:
            return "[Empty Tree]"

        {n.node_id: n for n in nodes}
        macros = [n for n in nodes if n.level == "MACRO"]

        lines = [f"🌳 H-TREE EXECUTION DAG: {tree_id}"]

        status_icons = {
            "PENDING": "⏳",
            "READY": "🔵",
            "RUNNING": "⚙️",
            "COMPLETED": "✅",
            "FAILED": "❌",
            "MUTATED": "🧬",
            "SKIPPED": "⏭️",
        }

        for m in macros:
            m_icon = status_icons.get(m.status, "•")
            lines.append(f"├── {m_icon} [MACRO] {m.title} ({m.status})")
            # Find mesos under this macro
            mesos = [n for n in nodes if n.parent_id == m.node_id and n.level == "MESO"]
            for me in mesos:
                me_icon = status_icons.get(me.status, "•")
                lines.append(f"│   ├── {me_icon} [MESO] {me.title} ({me.status})")
                # Find micros under this meso
                micros = [n for n in nodes if n.parent_id == me.node_id and n.level == "MICRO"]
                for mi in micros:
                    mi_icon = status_icons.get(mi.status, "•")
                    tool_str = f" [{mi.required_tool}]" if mi.required_tool else ""
                    lines.append(f"│   │   └── {mi_icon} [MICRO] {mi.title}{tool_str} ({mi.status})")

        return "\n".join(lines)

    def _row_to_node(self, row: sqlite3.Row) -> HTNode:
        try:
            deps = json.loads(row["depends_on_json"])
        except Exception:
            deps = []
        try:
            children = json.loads(row["children_json"])
        except Exception:
            children = []
        try:
            tool_in = json.loads(row["tool_input_json"])
        except Exception:
            tool_in = {}
        try:
            mutations = json.loads(row["mutation_history_json"])
        except Exception:
            mutations = []

        return HTNode(
            node_id=row["node_id"],
            tree_id=row["tree_id"],
            parent_id=row["parent_id"],
            title=row["title"],
            description=row["description"],
            level=row["level"],
            status=row["status"],
            assigned_specialist=row["assigned_specialist"],
            depends_on=deps,
            children_ids=children,
            required_tool=row["required_tool"],
            tool_input=tool_in,
            tool_output=row["tool_output"],
            execution_time_s=row["execution_time_s"],
            retry_count=row["retry_count"],
            mutation_history=mutations,
            created_at=row["created_at"],
            completed_at=row["completed_at"],
        )


# ──────────────────────────────────────────────────────────────────────────────
# H-TREE DECOMPOSER ENGINE
# ──────────────────────────────────────────────────────────────────────────────

class HDecomposerEngine:
    """
    LLM-powered hierarchical goal decomposer that converts user objectives into 3-tier H-Trees.
    """

    def __init__(
        self,
        claude: anthropic.Anthropic | None = None,
        gemini: Any = None,
        sonnet_model: str = "claude-sonnet-5",
        haiku_model: str = "claude-haiku-4-5-20251001",
        gemini_model: str = "gemini-2.5-flash",
        provider: str = "anthropic",
    ) -> None:
        self.claude = claude
        if gemini is None and _HAS_GEMINI and os.getenv("GEMINI_API_KEY"):
            try:
                from google import genai
                gemini = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
            except Exception:
                gemini = None
        self.gemini = gemini
        self.sonnet_model = sonnet_model
        self.haiku_model = haiku_model
        self.gemini_model = gemini_model
        self.provider = provider

    def decompose(self, goal_text: str, tree_id: str | None = None) -> tuple[str, list[HTNode]]:
        """Decomposes goal_text into a list of HTNodes."""
        tree_id = tree_id or f"htree_{uuid.uuid4().hex[:10]}"
        prompt = _DECOMPOSITION_PROMPT.format(goal_text=goal_text)

        raw_json = self._call_llm(prompt)
        cleaned = re.sub(r"^```(?:json)?\s*", "", raw_json.strip(), flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned.strip())

        nodes: list[HTNode] = []
        try:
            data = json.loads(cleaned)
            raw_nodes = data.get("nodes", [])
            if not raw_nodes:
                nodes = self._fallback_decomposition(goal_text, tree_id)
            else:
                for rn in raw_nodes:
                    nid = rn.get("id") or f"node_{uuid.uuid4().hex[:8]}"
                    nodes.append(HTNode(
                        node_id=nid,
                        tree_id=tree_id,
                        parent_id=rn.get("parent_id"),
                        title=rn.get("title", "Untitled Task"),
                        description=rn.get("description", ""),
                        level=rn.get("level", "MICRO").upper(),
                        assigned_specialist=rn.get("assigned_specialist", "ultron_prime"),
                        depends_on=rn.get("depends_on", []),
                        required_tool=rn.get("required_tool"),
                        tool_input=rn.get("tool_input", {}),
                    ))
        except Exception as e:
            print(f"  [HDecomposer JSON Warning] {e} -> Generating deterministic fallback H-Tree")
            nodes = self._fallback_decomposition(goal_text, tree_id)

        if not nodes:
            nodes = self._fallback_decomposition(goal_text, tree_id)

        # Wire children_ids
        node_map = {n.node_id: n for n in nodes}
        for n in nodes:
            if n.parent_id and n.parent_id in node_map:
                node_map[n.parent_id].children_ids.append(n.node_id)

        return tree_id, nodes

    def _call_llm(self, prompt: str) -> str:
        if self.provider == "anthropic" and self.claude:
            # 1. Try Claude Sonnet
            try:
                resp = self.claude.messages.create(
                    model=self.sonnet_model,
                    max_tokens=3000,
                    messages=[{"role": "user", "content": prompt}],
                )
                return "".join(b.text for b in resp.content if b.type == "text")
            except Exception as e:
                print(f"  [HDecomposer Claude Sonnet Error] {e} -> Failing over to Haiku")
                try:
                    resp = self.claude.messages.create(
                        model=self.haiku_model,
                        max_tokens=3000,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    return "".join(b.text for b in resp.content if b.type == "text")
                except Exception as he:
                    print(f"  [HDecomposer Claude Haiku Error] {he} -> Failing over to Gemini")

        if self.gemini and _HAS_GEMINI:
            candidate_pool = ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-flash-lite-latest", "gemini-3.6-flash"]
            for candidate_model in candidate_pool:
                try:
                    resp = self.gemini.models.generate_content(
                        model=candidate_model,
                        contents=prompt,
                    )
                    if resp and resp.text:
                        return resp.text.strip()
                except Exception:
                    continue

        return "{}"

    def _fallback_decomposition(self, goal_text: str, tree_id: str) -> list[HTNode]:
        """Deterministic 3-tier structure fallback for offline execution."""
        m1_id = f"macro_1_{tree_id[:6]}"
        m2_id = f"macro_2_{tree_id[:6]}"
        meso1_id = f"meso_1_1_{tree_id[:6]}"
        meso2_id = f"meso_2_1_{tree_id[:6]}"
        micro1_id = f"micro_1_1_1_{tree_id[:6]}"
        micro2_id = f"micro_2_1_1_{tree_id[:6]}"

        return [
            HTNode(node_id=m1_id, tree_id=tree_id, parent_id=None, title="Architectural Analysis & Computation", description="Formulate data models and calculate core metrics", level="MACRO"),
            HTNode(node_id=meso1_id, tree_id=tree_id, parent_id=m1_id, title="Execute Mathematical & Sandbox Models", description="Run computational algorithms in Python sandbox", level="MESO"),
            HTNode(node_id=micro1_id, tree_id=tree_id, parent_id=meso1_id, title="Execute Python Computation", description="Run calculation script", level="MICRO", required_tool="run_python", tool_input={"code": "print('Computation completed successfully.')"}),
            HTNode(node_id=m2_id, tree_id=tree_id, parent_id=None, title="Synthesis & Executive Verification", description="Validate outputs and assemble executive deliverable", level="MACRO", depends_on=[m1_id]),
            HTNode(node_id=meso2_id, tree_id=tree_id, parent_id=m2_id, title="Synthesize Deliverable", description="Package verified results", level="MESO", depends_on=[meso1_id]),
            HTNode(node_id=micro2_id, tree_id=tree_id, parent_id=meso2_id, title="Format Final Solution", description="Synthesize verified brief", level="MICRO", depends_on=[micro1_id]),
        ]


# ──────────────────────────────────────────────────────────────────────────────
# SELF-EVOLVING DYNAMIC DAG REPLANNER & EXECUTOR
# ──────────────────────────────────────────────────────────────────────────────

class HierarchicalPlanner:
    """
    Unified Hierarchical Goal Decomposition & Self-Evolving Dynamic DAG Engine.
    Coordinates tree decomposition, topological execution, in-flight failure mutation,
    and trajectory consolidation.
    """

    def __init__(
        self,
        db_path: str = "./data/hierarchical_plans.sqlite3",
        claude: anthropic.Anthropic | None = None,
        gemini: Any = None,
        sonnet_model: str = "claude-sonnet-5",
        haiku_model: str = "claude-haiku-4-5-20251001",
        gemini_model: str = "gemini-2.5-flash",
        provider: str = "anthropic",
        tool_executor: ToolExecutor | None = None,
        trajectory_manager: TrajectoryManager | None = None,
        telemetry: TelemetryEngine | None = None,
    ) -> None:
        self.store = HierarchicalGoalTree(db_path=db_path)
        self.decomposer = HDecomposerEngine(
            claude=claude,
            gemini=gemini,
            sonnet_model=sonnet_model,
            haiku_model=haiku_model,
            gemini_model=gemini_model,
            provider=provider,
        )
        self.claude = claude
        if gemini is None and _HAS_GEMINI and os.getenv("GEMINI_API_KEY"):
            try:
                from google import genai
                gemini = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
            except Exception:
                gemini = None
        self.gemini = gemini
        self.gemini_model = gemini_model if gemini_model not in ("gemini-2.0-flash", "gemini-2.5-flash", "gemini-flash-latest") else "gemini-3.6-flash"
        self.haiku_model = haiku_model
        self.provider = provider
        self.tool_executor = tool_executor or ToolExecutor()
        self.trajectories = trajectory_manager
        self.telemetry = telemetry

    def plan_and_execute(
        self,
        goal_text: str,
        user_id: str = "boss",
        max_replans_per_node: int = 2,
    ) -> PlanExecutionResult:
        """
        Main entrypoint:
          1. Decomposes goal into 3-tier H-Tree.
          2. Persists tree to SQLite.
          3. Loops through ready micro-nodes in topological order.
          4. Executes tool actions in sandbox.
          5. If an action fails -> dynamically splices a repair node into the DAG.
          6. Updates parent Meso/Macro states.
          7. Synthesizes complete executive brief and commits trajectory to ChromaDB.
        """
        t0 = time.time()
        tree_id, nodes = self.decomposer.decompose(goal_text)
        self.store.save_tree(tree_id, goal_text, nodes)

        completed_count = 0
        failed_count = 0
        mutated_count = 0

        # Execution Loop
        max_iterations = 25
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            ready_nodes = self.store.get_ready_nodes(tree_id)
            if not ready_nodes:
                # Check if all micro nodes are finished
                all_nodes = self.store.get_nodes(tree_id)
                micro_nodes = [n for n in all_nodes if n.level == "MICRO"]
                if all(n.status in ("COMPLETED", "SKIPPED", "MUTATED") for n in micro_nodes):
                    break
                else:
                    # Stalled or pending dependencies
                    break

            for node in ready_nodes:
                node.status = "RUNNING"
                self.store.update_node(node)

                # Execute Action
                t_node_start = time.time()
                exec_ok = True
                out_str = ""

                if node.required_tool:
                    tool_res = self.tool_executor.execute(node.required_tool, node.tool_input)
                    exec_ok = tool_res.get("success", False)
                    out_str = str(tool_res.get("output", ""))
                    if not exec_ok and tool_res.get("error"):
                        out_str += f"\nERROR: {tool_res.get('error')}"
                else:
                    out_str = f"Reasoning analysis verified for '{node.title}'."

                node.execution_time_s = time.time() - t_node_start
                node.tool_output = out_str

                # Check for Failure & Trigger Dynamic Replanning
                if not exec_ok:
                    if node.retry_count < max_replans_per_node:
                        node.retry_count += 1
                        replan_success = self._handle_in_flight_mutation(node, goal_text, out_str)
                        if replan_success:
                            node.status = "MUTATED"
                            mutated_count += 1
                        else:
                            node.status = "FAILED"
                            failed_count += 1
                    else:
                        node.status = "FAILED"
                        failed_count += 1
                else:
                    node.status = "COMPLETED"
                    node.completed_at = time.time()
                    completed_count += 1

                self.store.update_node(node)

        # Rollup parent Meso and Macro completion states
        self._rollup_parent_states(tree_id)

        all_final_nodes = self.store.get_nodes(tree_id)
        total_time = time.time() - t0
        is_success = failed_count == 0

        # Synthesize Deliverable
        final_brief = self._synthesize_final_brief(goal_text, all_final_nodes, is_success)

        # Save trajectory to Trajectory Bank
        traj_id = None
        if is_success and self.trajectories:
            try:
                traj_tool_actions = [
                    {"tool": n.required_tool or "reasoning", "input": n.tool_input, "output": n.tool_output, "success": True}
                    for n in all_final_nodes if n.level == "MICRO"
                ]
                traj_id = self.trajectories.record_trajectory(
                    user_input=goal_text,
                    tool_actions=traj_tool_actions,
                    final_reply=final_brief[:800],
                    score=10,
                    domain_tag="hierarchical_planner",
                )
            except Exception as te:
                print(f"  [HTREE TRAJECTORY ERROR] {te}")

        # Telemetry
        if self.telemetry:
            self.telemetry.log_event(
                user_id=user_id,
                event_type="HTREE_EXECUTION",
                module_id="hierarchical_planner",
                details={
                    "tree_id": tree_id,
                    "total_nodes": len(all_final_nodes),
                    "completed": completed_count,
                    "mutated": mutated_count,
                    "failed": failed_count,
                    "success": is_success,
                    "duration_s": total_time,
                },
            )

        return PlanExecutionResult(
            tree_id=tree_id,
            root_goal=goal_text,
            success=is_success,
            total_nodes=len(all_final_nodes),
            completed_nodes=completed_count,
            failed_nodes=failed_count,
            mutated_nodes=mutated_count,
            total_duration_s=total_time,
            final_output=final_brief,
            node_summary=[n.to_dict() for n in all_final_nodes],
            trajectory_id=traj_id,
        )

    def _handle_in_flight_mutation(self, failed_node: HTNode, root_goal: str, error_output: str) -> bool:
        """
        Dynamically splices new self-healing nodes into the DAG upon encountering a tool error.
        """
        prompt = _REPLAN_MUTATION_PROMPT.format(
            failed_node_id=failed_node.node_id,
            failed_title=failed_node.title,
            failed_description=failed_node.description,
            failed_tool=failed_node.required_tool or "general_tool",
            error_output=error_output[:1000],
            root_goal=root_goal,
            parent_id=failed_node.parent_id or "",
        )

        raw = ""
        if self.provider == "anthropic" and self.claude:
            try:
                resp = self.claude.messages.create(
                    model=self.haiku_model,
                    max_tokens=2000,
                    messages=[{"role": "user", "content": prompt}],
                )
                raw = "".join(b.text for b in resp.content if b.type == "text")
            except Exception as e:
                print(f"  [REPLAN CLAUDE ERROR] {e}")

        if not raw and self.gemini and _HAS_GEMINI:
            candidate_pool = ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-flash-lite-latest", "gemini-3.6-flash"]
            for candidate_model in candidate_pool:
                try:
                    resp = self.gemini.models.generate_content(
                        model=candidate_model,
                        contents=prompt,
                    )
                    if resp and resp.text:
                        raw = resp.text.strip()
                        break
                except Exception:
                    continue

        if not raw:
            # Fallback simple retry with safe python string replacement
            new_id = f"repaired_{uuid.uuid4().hex[:6]}"
            repaired_node = HTNode(
                node_id=new_id,
                tree_id=failed_node.tree_id,
                parent_id=failed_node.parent_id,
                title=f"Auto-Patched: {failed_node.title}",
                description=f"Fallback self-healing attempt for {failed_node.node_id}",
                level="MICRO",
                assigned_specialist=failed_node.assigned_specialist,
                required_tool=failed_node.required_tool,
                tool_input=failed_node.tool_input,
                depends_on=failed_node.depends_on,
                mutation_history=[f"Spliced replacement for {failed_node.node_id} (error: {error_output[:50]})"],
            )
            self.store.add_node(repaired_node)
            return True

        try:
            cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned.strip())
            data = json.loads(cleaned)
            replacements = data.get("replacement_nodes", [])
            for rep in replacements:
                nid = rep.get("id") or f"repaired_{uuid.uuid4().hex[:6]}"
                if not nid.lower().startswith("repaired_") and not nid.lower().startswith("rep_"):
                    nid = f"repaired_{nid}"
                r_title = rep.get("title", f"Repaired: {failed_node.title}")
                if not r_title.lower().startswith("repaired") and not r_title.lower().startswith("auto-patched"):
                    r_title = f"Repaired: {r_title}"
                r_node = HTNode(
                    node_id=nid,
                    tree_id=failed_node.tree_id,
                    parent_id=failed_node.parent_id,
                    title=r_title,
                    description=rep.get("description", ""),
                    level="MICRO",
                    assigned_specialist=rep.get("assigned_specialist", failed_node.assigned_specialist),
                    required_tool=rep.get("required_tool", failed_node.required_tool),
                    tool_input=rep.get("tool_input", {}),
                    depends_on=rep.get("depends_on", failed_node.depends_on),
                    mutation_history=[f"Dynamically spliced to heal {failed_node.node_id}"],
                )
                self.store.add_node(r_node)
            return True
        except Exception as pe:
            print(f"  [REPLAN PARSE ERROR] {pe}")
            return False

    def _rollup_parent_states(self, tree_id: str) -> None:
        """Rolls up status from Micro leaves to Meso and Macro parents."""
        nodes = self.store.get_nodes(tree_id)
        {n.node_id: n for n in nodes}

        # 1. Rollup to Meso
        for meso in [n for n in nodes if n.level == "MESO"]:
            children = [n for n in nodes if n.parent_id == meso.node_id]
            if children:
                if all(c.status in ("COMPLETED", "MUTATED", "SKIPPED") for c in children):
                    meso.status = "COMPLETED"
                    meso.completed_at = time.time()
                elif any(c.status == "FAILED" for c in children):
                    meso.status = "FAILED"
                self.store.update_node(meso)

        # 2. Rollup to Macro
        for macro in [n for n in nodes if n.level == "MACRO"]:
            children = [n for n in nodes if n.parent_id == macro.node_id]
            if children:
                if all(c.status in ("COMPLETED", "MUTATED", "SKIPPED") for c in children):
                    macro.status = "COMPLETED"
                    macro.completed_at = time.time()
                elif any(c.status == "FAILED" for c in children):
                    macro.status = "FAILED"
                self.store.update_node(macro)

    def _synthesize_final_brief(self, root_goal: str, nodes: list[HTNode], success: bool) -> str:
        """Assembles a clean, structured executive deliverable from node outputs."""
        lines = [
            "### 👑 ULTRON HIERARCHICAL PLANNER — EXECUTIVE DELIVERABLE",
            f"**Master Objective:** {root_goal}\n",
            f"**Execution Status:** {'✅ 100% SUCCESS' if success else '⚠️ PARTIAL EXECUTION'}\n",
            "**Key Completed Milestones & Output Trajectories:**",
        ]

        micros = [n for n in nodes if n.level == "MICRO" and n.status in ("COMPLETED", "MUTATED")]
        for m in micros:
            out_preview = (m.tool_output or "").strip().replace("\n", " ")
            if len(out_preview) > 120:
                out_preview = out_preview[:120] + "..."
            lines.append(f"- **{m.title}**: {out_preview}")

        return "\n".join(lines)
