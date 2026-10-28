"""
ultron.core.pipeline.context — Encapsulated context payload for the CognitivePipeline.

Holds all in-flight request, intermediate retrieval, model execution,
and verification state across pipeline stages.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PipelineContext:
    # ── Host / Agent Reference ──
    agent: Any

    # ── Request Invariants ──
    user_input: str
    files: list[Any] = field(default_factory=list)
    module_id: str = "ultron_prime"
    model_override: str | None = None
    optimize_prompt: bool = True
    operation_mode: str = "SWARM"
    client_data: bool = False

    # ── Execution Control ──
    effective_mode: str = "SWARM"
    is_terminated: bool = False
    early_result: dict[str, Any] | None = None

    # ── Context Stage Outputs ──
    effective_input: str = ""
    prompt_opt_payload: dict[str, Any] = field(default_factory=dict)
    selected_model: str = ""
    route_reason: str = ""
    query_text: str = ""
    search_query: str = ""
    memory_text: str = ""
    matched_skills_list: list[Any] = field(default_factory=list)
    skills_used_payload: list[dict[str, Any]] = field(default_factory=list)
    skill_context: str = ""
    traj_context: str = ""
    graph_context: str = ""
    tool_instruction: str = ""
    system_prompt: str = ""
    combined_text: str = ""
    text_attachments: list[Any] = field(default_factory=list)

    # ── Execution Stage Outputs ──
    tools_param: list[Any] = field(default_factory=list)
    tool_actions: list[dict[str, Any]] = field(default_factory=list)
    draft_reply: str = ""
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_write: int = 0
    total_cache_read: int = 0
    is_swarm: bool = False
    swarm_actions: list[Any] = field(default_factory=list)
    synthesizer_critic_applied: bool = False
    pre_synth_code_executed: bool = False

    # ── Verification Stage Outputs ──
    final_reply: str = ""

    # ── Telemetry & Diagnostics ──
    start_time: float = field(default_factory=time.time)

    def terminate_early(self, result: dict[str, Any]) -> None:
        """Mark context as completed early (e.g. lockdown, killswitch, fast-path)."""
        self.is_terminated = True
        self.early_result = result
