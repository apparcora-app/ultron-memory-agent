"""
ultron.core.pipeline.stages.verification_stage — Multi-Gate Verification & Sanitization stage.

Enforces:
1. Hard Execution Ledger Gate (Zero-Faking physical verification)
2. Zero-Trust Artifact Verification Gate (MINT self-healing contract)
3. In-Flight Pre-Response Critic Gate
4. Hidden Chain-of-Thought stripping (<thought> tags)
5. Deterministic Anti-Slop Sanitizer Gate
"""

from __future__ import annotations

import re
from typing import Any

from ultron.core.pipeline.context import PipelineContext


class VerificationStage:
    """Stage 3: Multi-Gate Verification, Ledger Enforcement & Anti-Slop Sanitization."""

    async def execute(self, ctx: PipelineContext) -> None:
        if ctx.is_terminated:
            return

        from ultron.agent import _sanitize_anti_slop

        assistant_reply = ctx.draft_reply
        tool_actions = ctx.tool_actions
        user_input = ctx.user_input
        combined_text = ctx.combined_text
        system_prompt = ctx.system_prompt

        # ── 1. Hard Execution Ledger Gate (Zero-Faking Enforcement) ──
        if hasattr(ctx.agent, "_ledger_gate") and ctx.agent._ledger_gate:
            try:
                assistant_reply, tool_actions, ledger_report = ctx.agent._ledger_gate.verify_and_enforce(
                    user_input=user_input or combined_text[:300],
                    draft_reply=assistant_reply,
                    tool_actions=tool_actions,
                    tool_executor=ctx.agent._tool_executor,
                )
                if ledger_report and not ledger_report.all_verified:
                    print("  [LEDGER GATE] Intercepted unverified physical execution claim.")
                    if ledger_report.failed_intents > 0:
                        assistant_reply = ctx.agent._call_raw_llm(
                            prompt=f"CRITICAL EXECUTION VIOLATION: {ledger_report.remediation_instructions}\nRewrite your response transparently stating what actually occurred based ONLY on real tool output.",
                            system_prompt=system_prompt,
                        )
            except Exception as gate_err:
                print(f"  [LEDGER GATE ERROR] {gate_err}")

        # ── 2. Zero-Trust Artifact Verification Gate ──
        if getattr(ctx.agent, "_artifact_gate", None) and tool_actions:
            try:
                contract = ctx.agent._artifact_gate.infer_contract(user_input or combined_text[:300], tool_actions)
                gate_result = ctx.agent._artifact_gate.verify(contract, tool_actions, assistant_reply)
                if not gate_result.passed:
                    print(f"  [ARTIFACT GATE] Intercepted missing artifacts: {gate_result.violations}")
                    violation_text = ", ".join(gate_result.violations)
                    correction_prompt = (
                        f"CRITICAL VERIFICATION FAILURE:\n"
                        f"You failed to satisfy the contract for {gate_result.contract_type}.\n"
                        f"Violations: {violation_text}\n"
                        f"Rewrite your response stating exactly what failed. Do NOT claim the task is complete."
                    )
                    corrected_reply = ctx.agent._call_raw_llm(
                        prompt=correction_prompt,
                        system_prompt=system_prompt,
                    )
                    if corrected_reply:
                        assistant_reply = corrected_reply
            except Exception as gate_err:
                print(f"  [ARTIFACT GATE ERROR] {gate_err}")

        # ── 3. In-Flight Pre-Response Critic Gate (Phase 4 Consolidated) ──
        is_complex = "COMPLEX" in (ctx.route_reason or "")
        has_tools = len(tool_actions) > 0

        # Phase 4 Latency & Token Optimization:
        # If single-pass synthesis already embedded Critic grounding directives,
        # bypass the redundant serial post-hoc LLM call unless complex multi-agent mode is flagged.
        should_run_critic = assistant_reply and has_tools and (not ctx.synthesizer_critic_applied or is_complex) and len(tool_actions) > 1

        if ctx.synthesizer_critic_applied and not should_run_critic and has_tools:
            print("  [GATE CONSOLIDATION] Critic directives embedded in single-pass synthesis; bypassing serial critic re-prompt.")

        if should_run_critic:
            try:
                critic_res = ctx.agent._critic.verify_in_flight(
                    user_input=user_input or combined_text[:300],
                    draft_reply=assistant_reply,
                    tool_actions=tool_actions,
                )
                if not critic_res.approved and critic_res.correction_instruction:
                    print(f"  [IN-FLIGHT CRITIC] Intercepted discrepancy: {critic_res.critique}")
                    context_dump = "\n".join([f"{act['tool']}: {act.get('result', '')[:1000]}" for act in tool_actions])
                    refine_prompt = (
                        f"CORRECTION DIRECTIVE:\n"
                        f"Discrepancy identified: {critic_res.critique}\n"
                        f"Correction needed: {critic_res.correction_instruction}\n\n"
                        f"--- CONTEXT AVAILABLE TO YOU ---\n"
                        f"Original Draft:\n{assistant_reply}\n\n"
                        f"Tool Context:\n{context_dump}\n\n"
                        f"Please produce the revised, verified, and complete final response for {ctx.agent.user_title}.\n"
                        f"Rules: NEVER mention critique. Speak authoritatively. Do not dump raw code."
                    )
                    corrected_reply = ctx.agent._call_raw_llm(
                        prompt=refine_prompt,
                        system_prompt=system_prompt,
                    )
                    if corrected_reply and len(corrected_reply) > 50:
                        cleaned_reply = re.sub(r"(?i)as noted in the pre-response verification critique,?\s*", "", corrected_reply).strip()
                        cleaned_reply = re.sub(r"(?i)based on the pre-response verification critique,?\s*", "", cleaned_reply).strip()
                        assistant_reply = cleaned_reply
            except Exception as crit_err:
                print(f"  [IN-FLIGHT CRITIC WARNING] Pre-response gate fallback: {crit_err}")

        # ── 4. Strip Hidden Chain-of-Thought (<thought> and <think>) ──
        if assistant_reply:
            thought_match = re.search(r"<(?:thought|think)>(.*?)(?:</(?:thought|think)>|$)", assistant_reply, flags=re.DOTALL)
            if thought_match and thought_match.group(1):
                thought_content = thought_match.group(1).strip()
                print(f"\n  [HIDDEN THOUGHT]\n  {thought_content.replace(chr(10), chr(10) + '  ')}\n")
            assistant_reply = re.sub(r"<(?:thought|think)>(?:.*?</(?:thought|think)>|.*$)", "", assistant_reply, flags=re.DOTALL).strip()

        # ── 5. Deterministic Anti-Slop Sanitizer Gate ──
        assistant_reply = _sanitize_anti_slop(assistant_reply, user_title=ctx.agent.user_title)

        ctx.tool_actions = tool_actions
        ctx.final_reply = assistant_reply
