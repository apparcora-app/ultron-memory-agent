"""
ultron.core.pipeline.dispatcher — CognitivePipeline Interceptor Dispatcher.

Orchestrates sequential cognitive stages:
  ContextStage -> ExecutionStage -> VerificationStage -> PostTurnPersistence
"""

from __future__ import annotations

import logging
from typing import Any

from ultron.core.pipeline.context import PipelineContext
from ultron.core.pipeline.stages.context_stage import ContextStage
from ultron.core.pipeline.stages.execution_stage import ExecutionStage
from ultron.core.pipeline.stages.verification_stage import VerificationStage

logger = logging.getLogger("ultron.core.pipeline.dispatcher")


class CognitivePipeline:
    """
    Modular execution engine decomposing the former monolithic MemoryAgent.chat_async()
    into discrete, verifiable interceptor stages.
    """

    def __init__(
        self,
        context_stage: ContextStage | None = None,
        execution_stage: ExecutionStage | None = None,
        verification_stage: VerificationStage | None = None,
    ) -> None:
        self.context_stage = context_stage or ContextStage()
        self.execution_stage = execution_stage or ExecutionStage()
        self.verification_stage = verification_stage or VerificationStage()

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        """
        Executes the three-stage cognitive pipeline.
        Returns the standardized chat response dictionary.
        """
        # ── Stage 1: Context & Ingestion ──
        await self.context_stage.execute(ctx)
        if ctx.is_terminated and ctx.early_result is not None:
            return ctx.early_result

        # ── Stage 2: Inference & Tool Execution ──
        await self.execution_stage.execute(ctx)
        if ctx.is_terminated and ctx.early_result is not None:
            return ctx.early_result

        # ── Stage 3: Verification & Sanitization ──
        await self.verification_stage.execute(ctx)

        # ── Post-Turn Bookkeeping & History ──
        files_count = len(ctx.files) if ctx.files else 0
        history_user_text = ctx.user_input or f"[Attached {files_count} files]"
        if ctx.text_attachments and ctx.user_input:
            history_user_text = f"{ctx.user_input} [With {len(ctx.text_attachments)} document(s)]"
        if ctx.tool_actions:
            history_user_text += f" [Executed {len(ctx.tool_actions)} system action(s)]"

        ctx.agent._history.append({"role": "user", "content": history_user_text})
        ctx.agent._history.append({"role": "assistant", "content": ctx.final_reply})
        ctx.agent._trim_history()

        # ── Memory Update Decision ──
        memory_signal_text = ctx.user_input or ctx.combined_text[:300]
        should_update = ctx.agent._should_update_memory(memory_signal_text)
        ctx.agent._budget.record_memory_update(skipped=not should_update)

        turn = [
            {"role": "user", "content": memory_signal_text},
            {"role": "assistant", "content": ctx.final_reply},
        ]

        if not should_update and not ctx.agent._is_filler(memory_signal_text):
            ctx.agent._turns_since_mem_update += 1

        # ── Token Accounting ──
        ctx.agent._budget.record_turn(
            model=ctx.selected_model,
            input_tokens=ctx.total_input_tokens,
            output_tokens=ctx.total_output_tokens,
            cache_write_tokens=ctx.total_cache_write,
            cache_read_tokens=ctx.total_cache_read,
        )

        # ── Supervised Background Persistence (Phase 2 Integration) ──
        matched_ids = [s.id for s in ctx.matched_skills_list] if ctx.matched_skills_list else None
        if hasattr(ctx.agent, "_learning_supervisor") and ctx.agent._learning_supervisor:
            ctx.agent._learning_supervisor.submit_turn(
                user_input=ctx.user_input or ctx.combined_text[:300],
                assistant_reply=ctx.final_reply,
                tool_actions=ctx.tool_actions,
                turn=turn,
                should_update=should_update,
                matched_skill_ids=matched_ids,
                skill_context=ctx.skill_context,
                user_id=ctx.agent.user_id,
            )

        return {
            "reply": ctx.final_reply,
            "model_used": ctx.selected_model,
            "model_display": ctx.route_reason,
            "route_reason": ctx.route_reason,
            "tool_actions": ctx.tool_actions,
            "skills_used": ctx.skills_used_payload,
            "prompt_optimization": ctx.prompt_opt_payload,
            "operation_mode": ctx.effective_mode,
            "is_swarm": False,
            "swarm_actions": [],
        }

    def drain(self, agent: Any, timeout: float = 5.0) -> bool:
        """Flushes and drains background supervisors."""
        if hasattr(agent, "_learning_supervisor") and agent._learning_supervisor:
            return agent._learning_supervisor.drain(timeout=timeout)
        return True

    def shutdown(self, agent: Any, timeout: float = 5.0) -> None:
        """Gracefully terminates background supervisors."""
        if hasattr(agent, "_learning_supervisor") and agent._learning_supervisor:
            agent._learning_supervisor.stop(timeout=timeout)
