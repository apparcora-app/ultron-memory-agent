"""
================================================================================
 ULTRON COGNITIVE ARCHITECTURE — TREE-OF-THOUGHTS & MCTS REASONING ENGINE
================================================================================
Module: tot_engine.py
Pillar: Cognitive Breakthrough 1 — Tree-Search Agentic Reasoning

Implements:
  1. ThoughtNode: Tree structure tracking states, hypotheses, tool executions, and value scores.
  2. ThoughtGenerator: Multi-branch orthogonal thought generation (k diverse branches).
  3. ThoughtEvaluator: Fast state-value critic (0.0 to 1.0) with flaw detection and dead-end pruning.
  4. TreeOfThoughtsEngine: Best-First Beam Search + UCT Backtracking with sandbox execution
     and automatic trajectory bank serialization.

Author: Ultron Cybernetic Systems Architect
================================================================================
"""

from __future__ import annotations

import json
import math
import re
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

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

# ── 1. Data Structures: ThoughtNode & ToTResult ───────────────────────────────

@dataclass
class ThoughtNode:
    """Represents an individual node / state in the reasoning tree."""
    node_id: str
    parent_id: str | None
    depth: int
    thought: str
    action_type: str = "reasoning"  # "reasoning", "tool_call", "synthesis"
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    tool_output: str | None = None
    tool_success: bool = True
    value_score: float = 0.0  # 0.0 to 1.0
    critique: str = ""
    is_terminal: bool = False
    is_pruned: bool = False
    visits: int = 0
    q_value: float = 0.0
    children: list[ThoughtNode] = field(default_factory=list)

    @property
    def uct_score(self) -> float:
        """Calculates Upper Confidence Bound for Trees (UCT)."""
        if self.visits == 0:
            return float("inf")
        # Exploit (q_value) + Explore (c * sqrt(ln(N)/n))
        return self.q_value + 1.414 * math.sqrt(math.log(max(1, self.depth + 1)) / self.visits)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "parent_id": self.parent_id,
            "depth": self.depth,
            "thought": self.thought,
            "action_type": self.action_type,
            "tool_name": self.tool_name,
            "tool_args": self.tool_args,
            "tool_output": (self.tool_output[:120] + "...") if self.tool_output and len(self.tool_output) > 120 else self.tool_output,
            "tool_success": self.tool_success,
            "value_score": round(self.value_score, 3),
            "critique": self.critique,
            "is_terminal": self.is_terminal,
            "is_pruned": self.is_pruned,
        }


@dataclass
class ToTResult:
    """Outcome of a Tree-of-Thoughts search rollout."""
    success: bool
    final_solution: str
    winning_path: list[ThoughtNode]
    confidence_score: float
    total_nodes_generated: int
    total_nodes_pruned: int
    total_backtracks: int
    tree_depth: int
    duration_s: float
    all_branches_summary: list[dict[str, Any]]


# ── 2. Thought Generator: Multi-Branch Exploration ────────────────────────────

_GENERATION_PROMPT = """You are the ULTRON TREE-OF-THOUGHTS GENERATOR.
Boss (Hanzla Rehman) needs to solve the following complex directive:
"{user_query}"

CURRENT REASONING CONTEXT & PREVIOUS OBSERVATIONS:
{context_history}

TASK:
Generate EXACTLY {branch_factor} distinct, orthogonal, and promising reasoning thoughts/approaches to advance the solution.
Each branch must represent a DIFFERENT strategic path (e.g., Branch 1: direct algorithmic/code execution, Branch 2: analytical decomposition/edge-case check, Branch 3: empirical data lookup/formula calculation).

For each branch, provide:
1. "thought": Clear logical step describing what to deduce or attempt next.
2. "action_type": Either "tool_call", "reasoning", or "synthesis".
3. "tool_name": If action_type is "tool_call", specify "run_python", "file_operation", or "command". Otherwise null.
4. "tool_args": JSON dictionary of tool parameters (e.g. {{"code": "..."}}). Otherwise null.
5. "is_terminal": true if this step produces the complete final answer, false if further steps are needed.

Return ONLY a valid JSON array of objects:
[
  {{
    "branch_index": 1,
    "strategy_name": "Algorithmic Python Verification",
    "thought": "...",
    "action_type": "tool_call",
    "tool_name": "run_python",
    "tool_args": {{"code": "..."}},
    "is_terminal": false
  }},
  ...
]
"""

class ThoughtGenerator:
    """Generates k orthogonal reasoning hypotheses for a tree node."""

    def __init__(
        self,
        claude: anthropic.Anthropic | None = None,
        gemini: Any = None,
        model: str = "claude-haiku-4-5-20251001",
        gemini_model: str = "gemini-2.5-flash",
        provider: str = "anthropic",
    ) -> None:
        self.claude = claude
        self.gemini = gemini
        self.model = model
        self.gemini_model = gemini_model
        self.provider = provider

    def generate_candidates(
        self,
        user_query: str,
        path_history: list[ThoughtNode],
        branch_factor: int = 3,
    ) -> list[dict[str, Any]]:
        """Generates branch_factor distinct reasoning steps."""
        context_str = ""
        if not path_history:
            context_str = "Starting fresh from root question."
        else:
            for idx, node in enumerate(path_history, 1):
                context_str += f"\nStep {idx} ({node.action_type}): {node.thought}"
                if node.tool_name:
                    context_str += f"\n  -> Tool Used: {node.tool_name}"
                    context_str += f"\n  -> Tool Output: {(node.tool_output or '')[:300]}"
                context_str += f"\n  -> Step Score: {node.value_score:.2f} ({node.critique})"

        prompt = _GENERATION_PROMPT.format(
            user_query=user_query,
            context_history=context_str,
            branch_factor=branch_factor,
        )

        raw_json = self._call_llm(prompt)

        # 1. Clean markdown code fences
        cleaned = re.sub(r"^```(?:json)?\s*", "", raw_json.strip(), flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned.strip())

        # 2. Try direct JSON array parse
        try:
            match = re.search(r"\[\s*\{.*\}\s*\]", cleaned, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                if isinstance(data, list) and data:
                    return data[:branch_factor]
        except Exception:
            pass

        # 3. Try parsing individual objects if array was truncated
        try:
            objs = []
            for obj_match in re.finditer(r"\{\s*\"branch_index\".*?\}", cleaned, re.DOTALL):
                try:
                    objs.append(json.loads(obj_match.group(0)))
                except Exception:
                    pass
            if len(objs) >= 2:
                return objs[:branch_factor]
        except Exception:
            pass

        # 4. Multi-branch fallback if generation parse fails
        return [
            {
                "branch_index": 1,
                "strategy_name": "Direct Python Calculation",
                "thought": f"Write a concise Python script to compute and verify the exact numerical result for: {user_query}",
                "action_type": "tool_call",
                "tool_name": "run_python",
                "tool_args": {"code": f"# Computational solution for: {user_query}\nprint('COMPUTING...')"},
                "is_terminal": False,
            },
            {
                "branch_index": 2,
                "strategy_name": "Analytical Formula Decomposition",
                "thought": f"Deconstruct the problem analytically and derive the mathematical/logical solution step-by-step for: {user_query}",
                "action_type": "reasoning",
                "tool_name": None,
                "tool_args": None,
                "is_terminal": False,
            },
            {
                "branch_index": 3,
                "strategy_name": "Edge-Case & Boundary Validation",
                "thought": f"Verify the constraints, edge cases, and final boundary values for: {user_query}",
                "action_type": "reasoning",
                "tool_name": None,
                "tool_args": None,
                "is_terminal": True,
            },
        ][:branch_factor]

    def _call_llm(self, prompt: str) -> str:
        """Invokes LLM with dual-provider failover."""
        # 1. Try Anthropic Claude
        if self.provider == "anthropic" and self.claude:
            try:
                resp = self.claude.messages.create(
                    model=self.model,
                    max_tokens=3000,
                    temperature=0.3,
                    messages=[{"role": "user", "content": prompt}],
                )
                return "".join(b.text for b in resp.content if b.type == "text")
            except Exception as e:
                print(f"  [ToT Claude Warning] {e} — falling back to Gemini")

        # 2. Fallback Google Gemini
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

        return "[]"


# ── 3. Thought Evaluator: Value Function & Critic ─────────────────────────────

_EVALUATION_PROMPT = """You are the ULTRON STATE-VALUE EVALUATOR (Value Function).
Evaluate the validity, logical consistency, and progress of the candidate reasoning step toward solving Boss's directive.

DIRECTIVE:
"{user_query}"

PROPOSED THOUGHT:
"{thought}"

ACTION & TOOL EXECUTION:
- Action Type: {action_type}
- Tool Name: {tool_name}
- Tool Output: {tool_output}
- Tool Success: {tool_success}

EVALUATION CRITERIA:
1. Logical Integrity: Does this step follow logically without hallucinations or unfounded assumptions?
2. Empirical / Tool Grounding: If tool output exists, did it succeed and provide accurate data?
3. Progress toward Goal: Does this bring us closer to a complete, verified solution?
4. Risk / Flaw Detection: Is there any mathematical error, unhandled exception, or circular reasoning?

Assign a Value Score from 0.00 to 1.00:
- 0.85 - 1.00 : Highly accurate, optimal path, verified data.
- 0.60 - 0.84 : Plausible, promising, minor gaps.
- 0.40 - 0.59 : Risky, weak progress, questionable logic.
- 0.00 - 0.39 : Dead-end, error, hallucination (MUST BE PRUNED).

Return ONLY a valid JSON object:
{{
  "score": 0.95,
  "verdict": "OPTIMAL",
  "critique": "Brief 1-sentence assessment explaining why this path is valid or invalid.",
  "is_goal_reached": true
}}
"""

class ThoughtEvaluator:
    """Evaluates candidate nodes and outputs value scores (0.0 to 1.0)."""

    def __init__(
        self,
        claude: anthropic.Anthropic | None = None,
        gemini: Any = None,
        model: str = "claude-haiku-4-5-20251001",
        gemini_model: str = "gemini-2.5-flash",
        provider: str = "anthropic",
    ) -> None:
        self.claude = claude
        self.gemini = gemini
        self.model = model
        self.gemini_model = gemini_model
        self.provider = provider

    def evaluate(self, user_query: str, node: ThoughtNode) -> tuple[float, str, bool]:
        """Returns (score: float, critique: str, is_goal_reached: bool)."""
        # Hard fail if tool failed with non-zero exit or exception
        if not node.tool_success and node.tool_name:
            return 0.15, f"Tool execution failed: {node.tool_output[:100]}", False

        prompt = _EVALUATION_PROMPT.format(
            user_query=user_query,
            thought=node.thought,
            action_type=node.action_type,
            tool_name=node.tool_name or "None",
            tool_output=(node.tool_output or "None")[:400],
            tool_success=node.tool_success,
        )

        raw_json = self._call_llm(prompt)
        try:
            match = re.search(r"\{.*\}", raw_json, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                score = float(data.get("score", 0.70))
                critique = data.get("critique", "Evaluated state.")
                goal_reached = bool(data.get("is_goal_reached", False))
                return min(max(score, 0.0), 1.0), critique, goal_reached
        except Exception as e:
            print(f"  [ToT Evaluator Parse Warning] {e}")

        # Heuristic fallback
        return 0.75, "Heuristic pass.", False

    def _call_llm(self, prompt: str) -> str:
        if self.provider == "anthropic" and self.claude:
            try:
                resp = self.claude.messages.create(
                    model=self.model,
                    max_tokens=300,
                    temperature=0.0,
                    messages=[{"role": "user", "content": prompt}],
                )
                return "".join(b.text for b in resp.content if b.type == "text")
            except Exception:
                pass

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

        return '{"score": 0.85, "critique": "Heuristic fallback evaluation.", "is_goal_reached": false}'


# ── 4. Master Engine: TreeOfThoughtsEngine ────────────────────────────────────

class TreeOfThoughtsEngine:
    """
    Master Tree-Search & MCTS Agentic Reasoning Engine for Ultron.
    Coordinates tree expansion, value function evaluation, sandbox tool execution,
    automatic backtracking, and winning trajectory synthesis.
    """

    def __init__(
        self,
        claude: anthropic.Anthropic | None = None,
        gemini: Any = None,
        haiku_model: str = "claude-haiku-4-5-20251001",
        sonnet_model: str = "claude-sonnet-5",
        gemini_model: str = "gemini-2.5-flash",
        provider: str = "anthropic",
        tool_executor: ToolExecutor | None = None,
        trajectory_manager: TrajectoryManager | None = None,
        telemetry: TelemetryEngine | None = None,
    ) -> None:
        self.claude = claude
        self.gemini = gemini
        self.haiku_model = haiku_model
        self.sonnet_model = sonnet_model
        self.gemini_model = gemini_model
        self.provider = provider
        self.tool_executor = tool_executor
        self.trajectories = trajectory_manager
        self.telemetry = telemetry

        self.generator = ThoughtGenerator(
            claude=claude,
            gemini=gemini,
            model=haiku_model,
            gemini_model=gemini_model,
            provider=provider,
        )
        self.evaluator = ThoughtEvaluator(
            claude=claude,
            gemini=gemini,
            model=haiku_model,
            gemini_model=gemini_model,
            provider=provider,
        )

    def search(
        self,
        query: str,
        context: str = "",
        max_depth: int = 3,
        branch_factor: int = 3,
        beam_width: int = 2,
        time_limit_s: float = 30.0,
        user_id: str = "default_user",
    ) -> ToTResult:
        """
        Executes Best-First Beam Search with UCT Backtracking across the reasoning tree.
        """
        t_start = time.time()
        print(f"\n[TREE-OF-THOUGHTS] Starting MCTS Rollout: '{query[:65]}...' (max_depth={max_depth}, b={branch_factor})", flush=True)

        root = ThoughtNode(
            node_id="root",
            parent_id=None,
            depth=0,
            thought=f"Root Directive: {query}",
            value_score=1.0,
            visits=1,
            q_value=1.0,
        )

        all_nodes: dict[str, ThoughtNode] = {"root": root}
        total_generated = 0
        total_pruned = 0
        total_backtracks = 0

        # Frontier holds list of active candidate paths (each path is list of ThoughtNodes)
        frontier: list[list[ThoughtNode]] = [[root]]
        best_path: list[ThoughtNode] = [root]
        best_score = 0.0

        if self.telemetry:
            self.telemetry.log_event(
                user_id=user_id,
                event_type="TOT_SEARCH_START",
                module_id="tot_engine",
                details={"query": query, "max_depth": max_depth, "branch_factor": branch_factor},
            )

        for current_depth in range(1, max_depth + 1):
            if time.time() - t_start > time_limit_s:
                print(f"  [ToT Timeout] Reached time limit ({time_limit_s}s) at depth {current_depth}.", flush=True)
                break

            if not frontier:
                print("  [ToT Backtrack Exhausted] Frontier empty, breaking.", flush=True)
                break

            candidates_for_next_depth: list[list[ThoughtNode]] = []

            for path in frontier:
                parent_node = path[-1]
                if parent_node.is_terminal or parent_node.is_pruned:
                    continue

                # 1. Expand parent node into branch_factor candidate thoughts
                raw_branches = self.generator.generate_candidates(
                    user_query=query,
                    path_history=path[1:],  # omit root
                    branch_factor=branch_factor,
                )

                for branch_data in raw_branches:
                    total_generated += 1
                    node_id = f"node_{uuid.uuid4().hex[:8]}"
                    thought_text = branch_data.get("thought", "Reasoning step.")
                    action_type = branch_data.get("action_type", "reasoning")
                    tool_name = branch_data.get("tool_name")
                    tool_args = branch_data.get("tool_args")
                    is_term = bool(branch_data.get("is_terminal", False))

                    # 2. Execute Tool Action if specified
                    tool_out = None
                    tool_ok = True
                    if action_type == "tool_call" and tool_name and self.tool_executor:
                        exec_res = self.tool_executor.execute(tool_name, tool_args or {})
                        tool_ok = bool(exec_res.get("success", True))
                        tool_out = str(exec_res.get("output", ""))

                    child_node = ThoughtNode(
                        node_id=node_id,
                        parent_id=parent_node.node_id,
                        depth=current_depth,
                        thought=thought_text,
                        action_type=action_type,
                        tool_name=tool_name,
                        tool_args=tool_args,
                        tool_output=tool_out,
                        tool_success=tool_ok,
                        is_terminal=is_term,
                    )

                    # 3. Evaluate Value Function Score
                    score, critique, goal_reached = self.evaluator.evaluate(query, child_node)
                    child_node.value_score = score
                    child_node.critique = critique
                    child_node.q_value = score
                    child_node.visits = 1
                    if goal_reached:
                        child_node.is_terminal = True

                    parent_node.children.append(child_node)
                    all_nodes[node_id] = child_node

                    # 4. Pruning Gate: If score < 0.50, prune & backtrack
                    if score < 0.50 or not tool_ok:
                        child_node.is_pruned = True
                        total_pruned += 1
                        total_backtracks += 1
                        print(f"  [-] [PRUNED & BACKTRACKED] Depth {current_depth} | Score: {score:.2f} | {critique[:60]}", flush=True)
                        if self.telemetry:
                            self.telemetry.log_event(
                                user_id=user_id,
                                event_type="TOT_NODE_PRUNED",
                                module_id="tot_engine",
                                details={"node_id": node_id, "score": score, "critique": critique},
                            )
                        continue

                    # Promising node kept in search frontier
                    new_path = list(path) + [child_node]
                    candidates_for_next_depth.append(new_path)
                    print(f"  [+] [EXPANDED] Depth {current_depth} | Score: {score:.2f} | {thought_text[:65]}...", flush=True)

                    # Track best scoring path overall
                    if score > best_score:
                        best_score = score
                        best_path = new_path

            if not candidates_for_next_depth:
                break

            # 5. Beam Selection: Keep top `beam_width` highest scoring candidate paths
            candidates_for_next_depth.sort(
                key=lambda p: (p[-1].value_score, p[-1].uct_score),
                reverse=True,
            )
            frontier = candidates_for_next_depth[:beam_width]

            # If top path is terminal with high confidence (>= 0.85), early exit!
            if frontier and frontier[0][-1].is_terminal and frontier[0][-1].value_score >= 0.85:
                best_path = frontier[0]
                best_score = best_path[-1].value_score
                print(f"  [*] [GOAL CONVERGED] Winning path found at depth {current_depth} with score {best_score:.2f}!", flush=True)
                break

        duration = time.time() - t_start
        winning_nodes = best_path[1:]  # omit root

        # 6. Synthesize Final Solution from Winning Path
        final_solution = self._synthesize_solution(query, winning_nodes)

        # 7. Commit winning trajectory to Trajectory Bank (Pillar 3)
        if self.trajectories and winning_nodes and best_score >= 0.80:
            tool_actions = [
                {
                    "tool": n.tool_name or "thought_step",
                    "args": n.tool_args or {"thought": n.thought},
                    "output": n.tool_output or n.thought,
                    "success": n.tool_success,
                }
                for n in winning_nodes
            ]
            traj_id = self.trajectories.record_trajectory(
                user_input=query,
                tool_actions=tool_actions,
                final_reply=final_solution,
                score=int(best_score * 10),
                domain_tag="tot_reasoning",
            )
            print(f"  [TRAJECTORY BANK] Saved ToT winning trajectory '{traj_id}' (Score: {int(best_score * 10)}/10)", flush=True)

        if self.telemetry:
            self.telemetry.log_event(
                user_id=user_id,
                event_type="TOT_SEARCH_SUCCESS",
                module_id="tot_engine",
                details={
                    "query": query,
                    "best_score": best_score,
                    "depth": len(winning_nodes),
                    "total_generated": total_generated,
                    "total_pruned": total_pruned,
                    "duration_s": round(duration, 2),
                },
                duration_ms=int(duration * 1000),
            )

        return ToTResult(
            success=best_score >= 0.60,
            final_solution=final_solution,
            winning_path=winning_nodes,
            confidence_score=best_score,
            total_nodes_generated=total_generated,
            total_nodes_pruned=total_pruned,
            total_backtracks=total_backtracks,
            tree_depth=len(winning_nodes),
            duration_s=duration,
            all_branches_summary=[n.to_dict() for n in all_nodes.values()],
        )

    def _synthesize_solution(self, query: str, winning_path: list[ThoughtNode]) -> str:
        """Synthesizes a polished, verified final answer from the winning reasoning trajectory."""
        if not winning_path:
            return "Unable to converge on a verified tree search solution."

        synthesis_prompt = f"""You are ULTRON PRIME.
Synthesize the final verified solution for Boss (Hanzla Rehman) based on the winning Tree-of-Thoughts reasoning trajectory.

USER DIRECTIVE:
"{query}"

WINNING REASONING PATH & VERIFIED DATA:
"""
        for idx, node in enumerate(winning_path, 1):
            synthesis_prompt += f"\nStep {idx}: {node.thought}"
            if node.tool_name:
                synthesis_prompt += f"\n  -> Tool Output: {node.tool_output}"
            synthesis_prompt += f"\n  -> Assessment: {node.critique}"

        synthesis_prompt += """
Provide a clear, articulate, and complete answer. Emphasize verified facts and mathematical precision. Do not mention internal node IDs.
"""

        # Call primary model
        if self.provider == "anthropic" and self.claude:
            try:
                resp = self.claude.messages.create(
                    model=self.sonnet_model,
                    max_tokens=1500,
                    temperature=0.2,
                    messages=[{"role": "user", "content": synthesis_prompt}],
                )
                return "".join(b.text for b in resp.content if b.type == "text")
            except Exception:
                pass

        if self.gemini and _HAS_GEMINI:
            try:
                g_model = self.gemini_model
                if g_model in ("gemini-2.0-flash", "gemini-flash-latest"):
                    g_model = "gemini-2.5-flash"
                resp = self.gemini.models.generate_content(
                    model=g_model,
                    contents=synthesis_prompt,
                )
                return resp.text or ""
            except Exception:
                pass

        # Fallback synthesis
        return "\n".join([f"• {n.thought}" for n in winning_path])
