"""
trajectory_manager.py — Episodic Trajectory Bank for Ultron Protocol (ExpeL-Style Replay).

Captures, indexes, and replays high-scoring (>= 9/10) multi-step tool execution sequences.
Stores winning traces in ChromaDB ('ultron_trajectories') with local dense vector embeddings.
Injects proven execution precedents into prompt context to achieve 1-shot problem solving.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TrajectoryStep:
    tool: str
    input_summary: str
    output_summary: str
    success: bool


@dataclass
class EpisodicTrajectory:
    id: str
    user_prompt: str
    domain_tag: str
    tool_sequence: list[str]
    steps: list[TrajectoryStep]
    final_outcome: str
    score: int = 10
    created_at: float = field(default_factory=time.time)


class TrajectoryManager:
    """
    Manages episodic memory of winning agentic trajectories.
    Enables ExpeL-style experience replay by retrieving proven tool sequences.
    """

    def __init__(
        self,
        chroma_path: str = "./data/chroma",
        enabled: bool = True,
    ) -> None:
        self.chroma_path = Path(chroma_path)
        self.chroma_path.mkdir(parents=True, exist_ok=True)
        self.enabled = enabled
        self._collection = None

        if self.enabled:
            self._init_collection()

    def _init_collection(self) -> None:
        """Initializes persistent ChromaDB collection for winning trajectories."""
        try:
            import chromadb
            client = chromadb.PersistentClient(path=str(self.chroma_path))
            self._collection = client.get_or_create_collection(
                name="ultron_trajectories",
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as e:
            print(f"  [TRAJECTORY BANK WARNING] Could not initialize ChromaDB: {e}")
            self._collection = None

    def record_trajectory(
        self,
        user_input: str,
        tool_actions: list[dict[str, Any]],
        final_reply: str,
        score: int = 10,
        domain_tag: str = "general",
    ) -> str | None:
        """
        Serializes and embeds a high-quality multi-step execution trajectory.
        Only records turns with score >= 9 and at least 1 tool action.
        """
        if not self.enabled or not self._collection:
            return None
        if score < 9 or not tool_actions:
            return None

        # Build trajectory steps
        steps: list[TrajectoryStep] = []
        tool_sequence: list[str] = []

        for a in tool_actions:
            tool_name = str(a.get("tool", "unknown"))
            tool_sequence.append(tool_name)

            raw_in = a.get("input", {})
            in_summary = json.dumps(raw_in)[:200] if isinstance(raw_in, (dict, list)) else str(raw_in)[:200]

            raw_out = str(a.get("output", "") or a.get("error", ""))[:300]
            steps.append(TrajectoryStep(
                tool=tool_name,
                input_summary=in_summary,
                output_summary=raw_out,
                success=bool(a.get("success", True)),
            ))

        # Generate unique deterministic hash ID
        traj_id = f"traj_{hashlib.sha256((user_input + domain_tag + str(time.time())).encode('utf-8')).hexdigest()[:16]}"

        trajectory = EpisodicTrajectory(
            id=traj_id,
            user_prompt=user_input.strip(),
            domain_tag=domain_tag.strip().lower(),
            tool_sequence=tool_sequence,
            steps=steps,
            final_outcome=final_reply[:800].strip(),
            score=score,
            created_at=time.time(),
        )

        # Dense searchable text representation
        doc_text = (
            f"Objective: {trajectory.user_prompt}\n"
            f"Domain: {trajectory.domain_tag}\n"
            f"Proven Tool Flow: {' -> '.join(trajectory.tool_sequence)}\n"
            f"Solution Summary: {trajectory.final_outcome[:400]}"
        )

        try:
            self._collection.upsert(
                ids=[traj_id],
                documents=[doc_text],
                metadatas=[{
                    "id": traj_id,
                    "domain_tag": trajectory.domain_tag,
                    "score": score,
                    "tool_sequence": ",".join(tool_sequence),
                    "payload_json": json.dumps({
                        "id": traj_id,
                        "user_prompt": trajectory.user_prompt,
                        "domain_tag": trajectory.domain_tag,
                        "tool_sequence": trajectory.tool_sequence,
                        "steps": [asdict(s) for s in trajectory.steps],
                        "final_outcome": trajectory.final_outcome,
                        "score": score,
                    }),
                }],
            )
            print(f"  [TRAJECTORY BANK] Saved winning trajectory '{traj_id}' ({' -> '.join(tool_sequence)})")
            return traj_id
        except Exception as e:
            print(f"  [TRAJECTORY BANK ERROR] Failed to record trajectory: {e}")
            return None

    def get_relevant_trajectory(
        self,
        query: str,
        domain_tag: str = "",
        min_similarity: float = 0.25,
    ) -> EpisodicTrajectory | None:
        """
        Retrieves the most semantically relevant winning trajectory from episodic memory.
        """
        if not self.enabled or not self._collection or not query.strip():
            return None

        try:
            query_res = self._collection.query(
                query_texts=[query],
                n_results=1,
            )
            if not query_res or not query_res.get("ids") or not query_res["ids"][0]:
                return None

            dist = query_res["distances"][0][0]
            sim = max(0.0, 1.0 - dist)
            if sim < min_similarity:
                return None

            meta = query_res["metadatas"][0][0]
            payload_json = meta.get("payload_json", "{}")
            data = json.loads(payload_json)

            steps = [TrajectoryStep(**s) for s in data.get("steps", [])]
            return EpisodicTrajectory(
                id=data.get("id", ""),
                user_prompt=data.get("user_prompt", ""),
                domain_tag=data.get("domain_tag", "general"),
                tool_sequence=data.get("tool_sequence", []),
                steps=steps,
                final_outcome=data.get("final_outcome", ""),
                score=data.get("score", 10),
            )
        except Exception as e:
            print(f"  [TRAJECTORY BANK QUERY WARNING] {e}")
            return None

    def format_trajectory_context(self, trajectory: EpisodicTrajectory | None) -> str:
        """
        Formats a winning trajectory into a concise, few-shot precedent block
        for direct injection into Ultron's LLM prompt.
        """
        if not trajectory:
            return ""

        step_lines = []
        for idx, step in enumerate(trajectory.steps[:5], 1):
            step_lines.append(
                f"  {idx}. `{step.tool}` -> In: {step.input_summary[:90]} | Out: {step.output_summary[:100]}"
            )
        steps_text = "\n".join(step_lines)
        flow_text = " -> ".join(f"`{t}`" for t in trajectory.tool_sequence)

        return (
            f"### ⚡ Proven Episodic Execution Precedent ({trajectory.domain_tag.upper()}):\n"
            f"Similar Past Directive: \"{trajectory.user_prompt}\"\n"
            f"Proven Tool Flow: {flow_text}\n"
            f"Verified Execution Trace:\n{steps_text}\n"
            f"Proven Resolution Summary:\n{trajectory.final_outcome[:350]}\n\n"
            f"Execution Mandate: Replicate this exact tool sequencing and verification pattern to complete the task in 1 shot."
        )

    def count(self) -> int:
        """Returns total count of stored trajectories in ChromaDB."""
        if not self._collection:
            return 0
        try:
            return self._collection.count()
        except Exception:
            return 0

    def list_trajectories(self, limit: int = 10) -> list[dict[str, Any]]:
        """Returns list of stored winning trajectories."""
        if not self._collection:
            return []
        try:
            results = self._collection.get(limit=limit)
            items = []
            if results and results.get("ids"):
                ids = results["ids"]
                metas = results.get("metadatas", [])
                docs = results.get("documents", [])
                for idx, tid in enumerate(ids):
                    meta = metas[idx] if idx < len(metas) else {}
                    doc = docs[idx] if idx < len(docs) else ""
                    raw_data = meta.get("data", "{}")
                    try:
                        data = json.loads(raw_data)
                    except Exception:
                        data = {}
                    items.append({
                        "id": tid,
                        "domain_tag": meta.get("domain_tag", "general"),
                        "user_prompt": doc,
                        "tool_sequence": data.get("tool_sequence", []),
                        "score": data.get("score", 10),
                    })
            return items
        except Exception as e:
            print(f"  [TRAJECTORY BANK LIST WARNING] {e}")
            return []

    def get_trajectory(self, trajectory_id: str) -> EpisodicTrajectory | None:
        """Fetches a specific trajectory by its ID."""
        if not self._collection:
            return None
        try:
            res = self._collection.get(ids=[trajectory_id])
            if not res or not res.get("ids"):
                return None
            meta = res["metadatas"][0]
            data = json.loads(meta.get("data", "{}"))
            steps = [TrajectoryStep(**s) for s in data.get("steps", [])]
            return EpisodicTrajectory(
                id=trajectory_id,
                domain_tag=meta.get("domain_tag", "general"),
                user_prompt=res["documents"][0],
                tool_sequence=data.get("tool_sequence", []),
                steps=steps,
                final_outcome=data.get("final_outcome", ""),
                score=data.get("score", 10),
            )
        except Exception as e:
            print(f"  [TRAJECTORY GET WARNING] {e}")
            return None

