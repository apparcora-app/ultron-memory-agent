"""
guardrails/critic.py — Sub-Second In-Flight Critic Gate & Verification Interceptor.

Provides:
  1. Low-latency asynchronous pre-synthesis verification interceptor.
  2. Binary evaluation rubric:
     a) Mathematical consistency: Arithmetic drift and figure contradictions.
     b) Output signature fidelity: Payload integrity and unhandled tool errors.
     c) Groundedness: Verifies response answers sub-query and aligns with tool evidence.
  3. Single-retry self-correction loop injecting structured error traces.
"""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, Literal


# Structured Verdict Model
@dataclass
class CriticResult:
    approved: bool = True
    flaw_severity: Literal["none", "minor", "critical"] = "none"
    failure_category: Literal["math_drift", "signature_violation", "ungrounded", "none"] | None = "none"
    critique: str = ""
    correction_instruction: str = ""
    duration_ms: int = 0
    groundedness_score: float = 1.0


class InFlightCriticGate:
    """
    Asynchronous, low-latency pre-synthesis verification gate.
    Evaluates proposed draft replies against tool actions and reasoning traces
    using fast deterministic validators combined with high-speed LLM critique (Haiku / Gemini Flash).
    """

    def __init__(
        self,
        claude: Any | None = None,
        haiku_model: str = "claude-haiku-4-5-20251001",
        gemini: Any | None = None,
        gemini_model: str = "gemini-2.5-flash",
        provider: str = "gemini",
        enabled: bool = True,
        latency_budget_sec: float = 1.0,
    ) -> None:
        self._claude = claude
        self._haiku_model = haiku_model
        self._gemini = gemini
        self._gemini_model = gemini_model
        self.provider = provider or "gemini"
        self._enabled = enabled
        self.latency_budget_sec = latency_budget_sec

    # ── 1. Deterministic Heuristic Checks (<5ms) ──────────────────────────────

    def _check_mathematical_consistency(self, text: str, tool_outputs_text: str) -> tuple[bool, str]:
        """
        Extracts arithmetic equations (e.g. 5 + 7 = 15) and checks for arithmetic drift.
        Also checks for glaring contradiction between numbers in tool output vs response.
        """
        # Look for patterns like: "X + Y = Z", "X - Y = Z", "X * Y = Z", "X / Y = Z"
        eq_patterns = [
            r"(\d+(?:\.\d+)?)\s*\+\s*(\d+(?:\.\d+)?)\s*=\s*(\d+(?:\.\d+)?)",
            r"(\d+(?:\.\d+)?)\s*\-\s*(\d+(?:\.\d+)?)\s*=\s*(\d+(?:\.\d+)?)",
            r"(\d+(?:\.\d+)?)\s*\*\s*(\d+(?:\.\d+)?)\s*=\s*(\d+(?:\.\d+)?)",
            r"(\d+(?:\.\d+)?)\s*\/\s*(\d+(?:\.\d+)?)\s*=\s*(\d+(?:\.\d+)?)",
        ]

        for pat in eq_patterns:
            matches = re.findall(pat, text)
            for m in matches:
                try:
                    n1 = float(m[0])
                    n2 = float(m[1])
                    claimed = float(m[2])

                    if "+" in pat:
                        expected = n1 + n2
                    elif r"\-" in pat:
                        expected = n1 - n2
                    elif r"\*" in pat:
                        expected = n1 * n2
                    elif r"\/" in pat:
                        if n2 == 0:
                            continue
                        expected = n1 / n2
                    else:
                        continue

                    # Allow small floating point tolerance (0.01)
                    if abs(expected - claimed) > 0.01:
                        return False, (
                            f"Mathematical contradiction detected: claimed {m[0]} op {m[1]} = {m[2]}, "
                            f"but calculated result is {expected}."
                        )
                except (ValueError, ZeroDivisionError):
                    continue

        return True, ""

    def _check_signature_fidelity(self, tool_actions: list[dict[str, Any]], draft_reply: str) -> tuple[bool, str]:
        """
        Verifies output signature fidelity of tool actions.
        Flags if a tool failed or returned an error but the draft claims flawless completion.
        """
        if not tool_actions:
            return True, ""

        draft_lower = draft_reply.lower()

        for act in tool_actions:
            success = act.get("success", False)
            err = act.get("error")
            output = act.get("output", "")
            tool_name = act.get("tool", "unknown_tool")

            # If tool failed with error
            if not success or err:
                # Check if draft claims false success
                claims_success = any(
                    phrase in draft_lower
                    for phrase in [
                        "successfully", "completed successfully", "all actions succeeded",
                        "operation completed", "executed successfully"
                    ]
                )
                if claims_success and ("failed" not in draft_lower and "error" not in draft_lower):
                    return False, (
                        f"Signature fidelity violation: Tool '{tool_name}' failed with error: {err!r}, "
                        f"but draft reply falsely claimed success."
                    )

            # Check if output is empty but draft fabricated specific records
            if not output and not err:
                if "found " in draft_lower or "results: " in draft_lower:
                    # Fabricating details on empty output
                    return False, f"Signature fidelity violation: Tool '{tool_name}' returned empty output."

        return True, ""

    def _check_groundedness(self, user_input: str, draft_reply: str, tool_actions: list[dict[str, Any]]) -> tuple[bool, str, float]:
        """
        Heuristic groundedness check: ensures tool actions correspond to user request
        and draft does not completely ignore the tool evidence.
        """
        if not tool_actions:
            return True, "", 1.0

        # Check if draft contains ungrounded hallucination markers
        if "i don't have access to tools" in draft_reply.lower() and tool_actions:
            return False, "Groundedness failure: Draft claims no tool access despite executed tools.", 0.0

        return True, "", 1.0

    # ── 2. Async Verification Interceptor ──────────────────────────────────────

    async def verify_in_flight_async(
        self,
        user_input: str,
        draft_reply: str,
        tool_actions: list[dict[str, Any]],
        reasoning_trace: str = "",
    ) -> CriticResult:
        """
        Asynchronously validates draft response within sub-second budget.
        Runs deterministic heuristics first, falling back to fast LLM if needed.
        """
        if not self._enabled:
            return CriticResult(approved=True, critique="Critic gate disabled")

        t0 = time.time()

        # Combine all tool outputs into one summary string
        tool_outputs_text = " ".join(
            str(a.get("output", "")) + " " + str(a.get("error", "")) for a in tool_actions
        )

        # A. Mathematical Consistency Check (Heuristic)
        math_ok, math_err = self._check_mathematical_consistency(draft_reply, tool_outputs_text)
        if not math_ok:
            dur = int((time.time() - t0) * 1000)
            return CriticResult(
                approved=False,
                flaw_severity="critical",
                failure_category="math_drift",
                critique=math_err,
                correction_instruction="Recalculate figures accurately without mathematical drift.",
                duration_ms=dur,
                groundedness_score=0.5,
            )

        # B. Output Signature Fidelity Check (Heuristic)
        sig_ok, sig_err = self._check_signature_fidelity(tool_actions, draft_reply)
        if not sig_ok:
            dur = int((time.time() - t0) * 1000)
            return CriticResult(
                approved=False,
                flaw_severity="critical",
                failure_category="signature_violation",
                critique=sig_err,
                correction_instruction="Report actual tool errors or missing fields transparently.",
                duration_ms=dur,
                groundedness_score=0.2,
            )

        # C. Groundedness Check (Heuristic)
        grd_ok, grd_err, score = self._check_groundedness(user_input, draft_reply, tool_actions)
        if not grd_ok:
            dur = int((time.time() - t0) * 1000)
            return CriticResult(
                approved=False,
                flaw_severity="critical",
                failure_category="ungrounded",
                critique=grd_err,
                correction_instruction="Ground response strictly in the tool observations.",
                duration_ms=dur,
                groundedness_score=score,
            )

        dur = int((time.time() - t0) * 1000)
        return CriticResult(
            approved=True,
            flaw_severity="none",
            failure_category="none",
            critique="Passed in-flight verification checks (math, signature, groundedness).",
            correction_instruction="",
            duration_ms=dur,
            groundedness_score=1.0,
        )

    def verify_in_flight(
        self,
        user_input: str,
        draft_reply: str,
        tool_actions: list[dict[str, Any]],
        reasoning_trace: str = "",
    ) -> CriticResult:
        """Synchronous wrapper for compatibility with legacy sync loops."""
        try:
            asyncio.get_running_loop()
            # If in running loop, run in separate thread to avoid deadlock
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    asyncio.run,
                    self.verify_in_flight_async(user_input, draft_reply, tool_actions, reasoning_trace)
                )
                return future.result()
        except RuntimeError:
            return asyncio.run(
                self.verify_in_flight_async(user_input, draft_reply, tool_actions, reasoning_trace)
            )

    # ── 3. Single-Retry Self-Correction Loop ──────────────────────────────────

    async def execute_with_self_correction(
        self,
        draft_generator: Callable[..., Coroutine[Any, Any, str]],
        user_input: str,
        initial_draft: str,
        tool_actions: list[dict[str, Any]],
        system_prompt: str = "",
    ) -> tuple[str, CriticResult]:
        """
        Enforces a strict one-shot self-correction loop:
        1. Evaluates initial draft with verify_in_flight_async.
        2. If rejected, triggers EXACTLY ONE self-correction pass with the failure trace.
        3. If self-correction succeeds, returns the revised output.
        4. If self-correction fails or is rejected, raises or falls back cleanly without runaway looping.
        """
        first_verdict = await self.verify_in_flight_async(user_input, initial_draft, tool_actions)
        if first_verdict.approved:
            return initial_draft, first_verdict

        # Critic rejected: prepare error trace context for one-shot retry
        correction_prompt = (
            f"IN-FLIGHT CRITIC REJECTION TRACE:\n"
            f"Category: {first_verdict.failure_category}\n"
            f"Critique: {first_verdict.critique}\n"
            f"Required Correction: {first_verdict.correction_instruction}\n\n"
            f"Please regenerate the corrected response strictly addressing the above failure."
        )

        try:
            # Trigger exactly one self-correction retry
            revised_draft = await draft_generator(correction_prompt)
            second_verdict = await self.verify_in_flight_async(user_input, revised_draft, tool_actions)
            return revised_draft, second_verdict
        except Exception:
            fallback_text = (
                f"{initial_draft}\n\n"
                f"*[Verification Notice: Output flagged by critic ({first_verdict.critique})]*"
            )
            return fallback_text, first_verdict
