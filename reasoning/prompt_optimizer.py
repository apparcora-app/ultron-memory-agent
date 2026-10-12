"""
prompt_optimizer.py — Autonomous Prompt Optimization Pre-Processor Agent for Ultron.

Intercepts user directives and applies 58 proven prompting frameworks
(from ./skills/prompt-optimizer/references/prompt-techniques.md)
to harden, clarify, and structure prompts before execution by Ultron / Swarm.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

# Heuristic bypass list for low-complexity / chit-chat messages
_BYPASS_PATTERNS = re.compile(
    r"^("
    r"hi|hello|hey|greetings|yo|sup"
    r"|yes|no|yep|nope|sure|ok|okay|alright|fine|thanks|thank you|cool|great"
    r"|status|clear|reset|help|exit|quit|ping"
    r"|open (chrome|browser|explorer|notepad|code)"
    r"|what is your name|who are you|how are you"
    r")[\s!.?]*$",
    re.IGNORECASE,
)


@dataclass
class OptimizationResult:
    original_prompt: str
    optimized_prompt: str
    applied: bool
    techniques: list[str] = field(default_factory=list)
    reasoning: str = ""
    duration_ms: int = 0


class PromptOptimizerAgent:
    """
    Ultron Pre-Processor Agent that intercepts raw directives, expands ambiguities,
    anchors constraints, and structures prompts using proven prompting frameworks.
    """

    def __init__(
        self,
        call_llm_fn: Callable[[str, str], str] | None = None,
        telemetry: Any = None,
    ) -> None:
        self._call_llm = call_llm_fn
        self._telemetry = telemetry

        # System instructions synthesized from 58 prompting techniques
        self.system_prompt = (
            "You are the ULTRON PROMPT ARCHITECT — an elite pre-processing intelligence dedicated to "
            "optimizing and hardening user directives for the Ultron Multi-Agent AI Mainframe.\n"
            "Your objective: Transform raw user prompts into high-precision, unambiguous, production-grade directives "
            "using established prompting techniques (Chain of Thought, Constraint Anchoring, Few-Shot Structuring, "
            "Role Definition, and Output Schema Specification).\n\n"
            "STRICT RULES:\n"
            "1. ZERO INTENT DRIFT: Preserve 100% of the user's original goal. Never change their objective.\n"
            "2. CLARIFY AMBIGUITY: Specify expected format, edge cases, error handling, and component boundaries.\n"
            "3. ACTION-ORIENTED: Structure the prompt with clear directives. CRITICAL: NEVER instruct the AI to 'write a script' or 'provide code'. Instruct the AI to 'USE YOUR TOOLS to execute the task and give me the answer'.\n"
            "4. RETURN STRICT JSON: You must ONLY output a JSON object with 'optimized_prompt', 'techniques', and 'reasoning'."
        )

    def should_bypass(self, text: str) -> bool:
        """Determines if a prompt is too simple or short to warrant LLM optimization."""
        if not text:
            return True
        cleaned = text.strip()
        words = cleaned.split()
        if len(words) < 8 or len(cleaned) < 60:
            return True
        if _BYPASS_PATTERNS.match(cleaned):
            return True
        # Direct action commands don't need expansion
        first_word = words[0].lower() if words else ""
        if first_word in ("run", "open", "check", "draft", "send", "search", "read", "write", "list", "show", "tell", "what", "how", "where", "who", "why"):
            return True
        return False

    def optimize(
        self,
        raw_prompt: str,
        enabled: bool = True,
        user_id: str = "boss",
    ) -> OptimizationResult:
        """
        Optimizes a user prompt. Returns an OptimizationResult with the original and optimized text.
        """
        t0 = time.time()

        # Check enabled and bypass heuristics
        if not enabled or not self._call_llm or self.should_bypass(raw_prompt):
            return OptimizationResult(
                original_prompt=raw_prompt,
                optimized_prompt=raw_prompt,
                applied=False,
                techniques=[],
                reasoning="Bypassed by heuristic filter (short query or disabled).",
                duration_ms=0,
            )

        optimization_instruction = f"""Analyze this user directive and rewrite it into an optimal, high-performance prompt:

RAW USER DIRECTIVE:
\"\"\"{raw_prompt}\"\"\"

Select 2 to 4 appropriate techniques from the following catalog:
- "Chain of Thought (CoT)"
- "Role & Objective Clarification"
- "Constraint & Boundary Anchoring"
- "Explicit Output Schema"
- "Ambiguity & Edge-Case Expansion"
- "Step-by-Step Task Decomposition"

Return a JSON object in this exact schema:
{{
  "optimized_prompt": "The complete, enhanced prompt with expanded details, formatting, and constraints",
  "techniques": ["Technique 1", "Technique 2"],
  "reasoning": "Brief rationale of improvements made"
}}

Output ONLY the raw JSON object. No markdown fences, no conversational preamble.
"""

        try:
            raw_response = self._call_llm(optimization_instruction, self.system_prompt)
            # Strip markdown fences if present
            cleaned_json = re.sub(r"^```json\s*", "", raw_response.strip())
            cleaned_json = re.sub(r"^```\s*", "", cleaned_json)
            cleaned_json = re.sub(r"\s*```$", "", cleaned_json)

            data = json.loads(cleaned_json)
            optimized_text = data.get("optimized_prompt", "").strip() or raw_prompt
            techniques = data.get("techniques", ["Prompt Structuring"])
            reasoning = data.get("reasoning", "Enhanced clarity and output constraints.")
            duration_ms = int((time.time() - t0) * 1000)

            # Record telemetry
            if self._telemetry:
                self._telemetry.log_event(
                    user_id=user_id,
                    event_type="PROMPT_OPTIMIZED",
                    module_id="prompt_optimizer",
                    details={
                        "original_length": len(raw_prompt),
                        "optimized_length": len(optimized_text),
                        "techniques": techniques,
                        "reasoning": reasoning,
                    },
                    duration_ms=duration_ms,
                )

            return OptimizationResult(
                original_prompt=raw_prompt,
                optimized_prompt=optimized_text,
                applied=True,
                techniques=techniques,
                reasoning=reasoning,
                duration_ms=duration_ms,
            )

        except Exception as err:
            duration_ms = int((time.time() - t0) * 1000)
            # Self-healing fallback: return original prompt on any error
            return OptimizationResult(
                original_prompt=raw_prompt,
                optimized_prompt=raw_prompt,
                applied=False,
                techniques=[],
                reasoning=f"Optimization fallback due to error: {err}",
                duration_ms=duration_ms,
            )
