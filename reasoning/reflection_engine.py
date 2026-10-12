"""
reflection_engine.py — Ultron Autonomous Self-Learning & In-Flight Verification Engine.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from skill_evolution import SkillMutator

SKILLS_DIR = Path(__file__).parent / "skills"

_GEMINI_COOLDOWN_UNTIL = 0.0

def _is_gemini_available() -> bool:
    global _GEMINI_COOLDOWN_UNTIL
    return time.time() > _GEMINI_COOLDOWN_UNTIL

def _trigger_gemini_cooldown(seconds: float = 60.0) -> None:
    global _GEMINI_COOLDOWN_UNTIL
    _GEMINI_COOLDOWN_UNTIL = time.time() + seconds

_CRITIC_PROMPT = """\
You are the ULTRON PRE-RESPONSE VERIFICATION CRITIC.
Inspect the assistant's proposed response and verify its factual, logical, and tool-output integrity before it is sent to Boss.

NOTE ON IDENTITY: Ultron is an autonomous cybernetic assistant with native tools (Python sandbox, file operations, web browsing, MCP servers, and vector memory). Do NOT critique Ultron's persona, system architecture, or capabilities.

USER'S DIRECTIVE:
{user_input}

PROPOSED DRAFT RESPONSE:
{draft_reply}

SYSTEM TOOL ACTIONS & TERMINAL LOGS:
{tool_summary}

VERIFICATION CHECKLIST:
1. Tool Consistency: Does the draft response accurately reflect the actual stdout/stderr outputs? (Flag if the draft claims success on an action that returned an error or empty output).
2. Numerical & Logic Consistency: Are numbers, calculations, and code snippets free of syntax bugs or contradictions?
3. Completeness: Did the draft address the user's core question or skip critical instructions?

Respond in EXACTLY this JSON shape - no markdown wrappers, no conversational text:
{{"approved": <true|false>, "flaw_severity": "<none|minor|critical>", "critique": "<one clear sentence explaining the discrepancy or why it is approved>", "correction_instruction": "<exact guidance on what to fix if approved is false, else empty string>"}}
"""

_REFLECT_PROMPT = """\
You are a quality evaluator for an AI assistant called Ultron.
Evaluate the following interaction between Boss and Ultron, and return a JSON evaluation.

USER DIRECTIVE:
{user_input}

ASSISTANT RESPONSE:
{assistant_reply}

  3-4:  Substantially wrong, hallucinated facts, or key failure.
  0-2:  Completely wrong, tool error unhandled, or dangerous output.
"""

_SKILL_DISTILL_PROMPT = """\
You are distilling a successful AI interaction into a reusable skill protocol.

USER ASKED:
{user_input}

ULTRON'S SUCCESSFUL RESPONSE:
{assistant_reply}

TOPIC DOMAIN: {topic_label}

Write a SKILL.md document in EXACTLY this format. No extra text before or after:

---
name: {skill_name}
description: {skill_description}
category: Auto-Learned
icon: 🧠
tags: [{tags}]
---

# {skill_name}

## When To Use
<one sentence describing the specific problem type this covers>

## Execution Protocol
<3-6 bullet points distilling the proven approach from the response above>

## Key Principles
<2-4 principles that made this solution successful>
"""


@dataclass
class CriticResult:
    approved: bool = True
    flaw_severity: str = "none"
    critique: str = ""
    correction_instruction: str = ""
    duration_ms: int = 0


@dataclass
class ReflectionResult:
    score: int = 0
    failure_type: str = "none"
    lesson_text: str = ""
    topic_label: str = ""
    lesson_stored: bool = False
    skill_written: bool = False
    skill_id: str = ""
    trajectory_id: str = ""
    skill_evolved: bool = False
    evolved_skill_id: str = ""
    new_version: str = ""
    duration_ms: int = 0


class InFlightCritic:
    """
    Fast pre-response verification critic.
    Evaluates proposed responses and tool executions in-flight before the final output is streamed to the user.
    """
    def __init__(self, claude: Any | None = None, haiku_model: str = "claude-haiku-4-5-20251001",
                 gemini: Any | None = None, gemini_model: str = "gemini-3.5-flash",
                 provider: str = "gemini",
                 enabled: bool = True) -> None:
        self._claude = claude
        self._haiku_model = haiku_model
        self._gemini = gemini
        self._gemini_model = gemini_model
        self.provider = provider or "gemini"
        self._enabled = enabled

    def verify_in_flight(self, user_input: str, draft_reply: str,
                         tool_actions: list[dict[str, Any]]) -> CriticResult:
        if not self._enabled:
            return CriticResult(approved=True, critique="Critic disabled")

        if not tool_actions:
            return CriticResult(approved=True, critique="Conversational turn skipped")

        t_start = time.time()
        tool_summary_lines = []
        for a in tool_actions[:8]:
            status = "SUCCESS" if a.get("success") else "FAILED"
            out = str(a.get("output", "") or a.get("error", ""))[:300]
            tool_summary_lines.append(f"• Tool: {a.get('tool')} [{status}] -> Output: {out}")
        tool_summary = "\n".join(tool_summary_lines) if tool_summary_lines else "None (Pure reasoning turn)"

        prompt = _CRITIC_PROMPT.format(
            user_input=user_input[:800],
            draft_reply=draft_reply[:1500],
            tool_summary=tool_summary,
        )

        raw = ""
        if self._gemini:
            candidate_pool = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-flash-lite-latest", "gemini-3.5-flash", "gemini-3.6-flash"]
            for candidate_model in candidate_pool:
                try:
                    resp = self._gemini.models.generate_content(
                        model=candidate_model,
                        contents=prompt,
                    )
                    raw = (resp.text or "").strip()
                    if raw:
                        break
                except Exception:
                    continue

        if not raw:
            return CriticResult(approved=True, critique="Critic check skipped")

        try:
            raw_clean = re.sub(r"^```(?:json)?\s*", "", raw)
            raw_clean = re.sub(r"\s*```$", "", raw_clean)
            match = re.search(r"\{[\s\S]*\}", raw_clean)
            if match:
                data = json.loads(match.group(0), strict=False)
            else:
                data = json.loads(raw_clean, strict=False)

            approved = bool(data.get("approved", True))
            flaw_severity = str(data.get("flaw_severity", "none")).lower()
            critique = str(data.get("critique", "")).strip()
            correction = str(data.get("correction_instruction", "")).strip()

            if flaw_severity == "minor":
                approved = True

            dur = int((time.time() - t_start) * 1000)
            return CriticResult(
                approved=approved,
                flaw_severity=flaw_severity,
                critique=critique,
                correction_instruction=correction,
                duration_ms=dur,
            )

        except Exception as e:
            print(f"  [IN-FLIGHT CRITIC WARNING] Verification pass skipped: {e}")
            dur = int((time.time() - t_start) * 1000)
            return CriticResult(approved=True, critique=f"Fallback: {e}", duration_ms=dur)


class SkillAutoWriter:
    def __init__(self, claude: Any | None = None, haiku_model: str = "claude-haiku-4-5-20251001",
                 gemini: Any | None = None, gemini_model: str = "gemini-flash-latest",
                 skills_dir: Path = SKILLS_DIR, min_score: int = 8,
                 auto_prefix: str = "auto_") -> None:
        self._claude = claude
        self._haiku_model = haiku_model
        self._gemini = gemini
        self._gemini_model = gemini_model
        self._skills_dir = skills_dir
        self._min_score = min_score
        self._auto_prefix = auto_prefix

    def _skill_already_exists(self, topic_label: str) -> bool:
        return (self._skills_dir / f"{self._auto_prefix}{topic_label}").exists()

    def maybe_write_skill(self, topic_label: str, user_input: str,
                          assistant_reply: str, score: int,
                          skill_matched: bool) -> str | None:
        if score < self._min_score or skill_matched:
            return None
        if self._skill_already_exists(topic_label):
            return None
        if len(assistant_reply) < 200:
            return None

        skill_name = topic_label.replace("_", " ").title() + " Protocol"
        skill_description = f"Auto-learned protocol for {topic_label.replace('_', ' ')} tasks."
        tags = ", ".join(topic_label.split("_"))

        prompt = _SKILL_DISTILL_PROMPT.format(
            user_input=user_input[:800],
            assistant_reply=assistant_reply[:1200],
            topic_label=topic_label,
            skill_name=skill_name,
            skill_description=skill_description,
            tags=tags,
        )

        try:
            if self._gemini:
                resp = self._gemini.models.generate_content(
                    model=self._gemini_model,
                    contents=prompt,
                )
                skill_content = (resp.text or "").strip()
            elif self._claude:
                response = self._claude.messages.create(
                    model=self._haiku_model, max_tokens=800,
                    messages=[{"role": "user", "content": prompt}],
                )
                skill_content = response.content[0].text.strip()
            else:
                return None
        except Exception as e:
            print(f"  [SKILL AUTO-WRITE] Skill distillation failed: {e}")
            return None

        if not skill_content.startswith("---"):
            return None

        clean_topic = re.sub(r"[^a-zA-Z0-9_-]", "_", topic_label.lower())
        skill_id = f"{self._auto_prefix}{clean_topic}"
        skill_folder = self._skills_dir / skill_id
        skill_folder.mkdir(parents=True, exist_ok=True)

        with open(skill_folder / "SKILL.md", "w", encoding="utf-8") as f:
            f.write(skill_content)

        print(f"  [SKILL AUTO-WRITE] Written: {skill_folder / 'SKILL.md'}")
        return skill_id


class ReflectionEngine:
    """Scores responses and applies autonomous learning (lessons + skill writing + skill evolution)."""

    def __init__(self, claude: Any | None = None, memory_manager: Any = None,
                 trajectory_manager: Any = None,
                 haiku_model: str = "claude-haiku-4-5-20251001",
                 gemini: Any | None = None, gemini_model: str = "gemini-flash-latest",
                 provider: str = "anthropic",
                 skills_dir: Path = SKILLS_DIR,
                 enabled: bool = True, cooldown_turns: int = 2,
                 max_fail_score: int = 5, min_skill_score: int = 8,
                 auto_skill_prefix: str = "auto_",
                 skill_manager: Any | None = None,
                 skill_mutator: Any | None = None) -> None:
        self._claude = claude
        self._gemini = gemini
        self._gemini_model = gemini_model
        self._memory = memory_manager
        self._trajectory_mgr = trajectory_manager
        self._haiku_model = haiku_model
        self.provider = provider
        self._enabled = enabled
        self._cooldown_turns = cooldown_turns
        self._max_fail_score = max_fail_score
        self._turns_since_last_reflect = 0
        self._skill_manager = skill_manager

        self._skill_writer = SkillAutoWriter(
            claude=claude, haiku_model=haiku_model,
            gemini=gemini, gemini_model=gemini_model,
            skills_dir=skills_dir,
            min_score=min_skill_score, auto_prefix=auto_skill_prefix,
        )
        self._skill_mutator = skill_mutator or SkillMutator(
            claude=claude, haiku_model=haiku_model,
            gemini=gemini, gemini_model=gemini_model,
            provider=provider,
            skills_dir=skills_dir,
            skill_manager=skill_manager,
        )

    def _format_tool_summary(self, tool_actions: list[dict]) -> str:
        if not tool_actions:
            return "None"
        lines = []
        for a in tool_actions[:5]:
            status = "OK" if a.get("success") else "FAILED"
            out_preview = str(a.get("output", ""))[:120]
            lines.append(f"  [{status}] {a.get('tool', 'unknown')}: {out_preview}")
        return "\n".join(lines)

    def reflect(self, user_input: str, assistant_reply: str,
                tool_actions: list[dict[str, Any]],
                skill_matched: bool = False,
                matched_skill_ids: list[str] | None = None) -> ReflectionResult:
        result = ReflectionResult()

        if not self._enabled:
            return result

        self._turns_since_last_reflect += 1
        if self._turns_since_last_reflect < self._cooldown_turns:
            return result
        if len(assistant_reply) < 80:
            return result

        self._turns_since_last_reflect = 0
        t_start = time.time()

        prompt = _REFLECT_PROMPT.format(
            user_input=user_input[:600],
            assistant_reply=assistant_reply[:1000],
            tool_summary=self._format_tool_summary(tool_actions),
        )

        raw = ""
        if self._gemini:
            candidate_pool = ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-flash-lite-latest", "gemini-3.6-flash"]
            for candidate_model in candidate_pool:
                try:
                    resp = self._gemini.models.generate_content(
                        model=candidate_model,
                        contents=prompt,
                    )
                    raw = (resp.text or "").strip()
                    if raw:
                        break
                except Exception:
                    continue

        if not raw:
            return result

        try:
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            match = re.search(r"\{[\s\S]*\}", raw)
            if match:
                data = json.loads(match.group(0), strict=False)
            else:
                data = json.loads(raw, strict=False)

            result.score = int(data.get("score", 7))
            result.failure_type = str(data.get("failure_type", "none"))
            result.lesson_text = str(data.get("lesson", "")).strip()
            result.topic_label = re.sub(
                r"[^a-z0-9_]", "_",
                str(data.get("topic_label", "general")).lower().strip()
            )[:40]
            is_novel_success = bool(data.get("is_novel_success", False))

        except Exception as e:
            print(f"  [REFLECTION] Scoring failed: {e}")
            result.duration_ms = int((time.time() - t_start) * 1000)
            return result

        # Store lesson if quality was poor
        if result.score <= self._max_fail_score and result.lesson_text:
            lesson_memory = (
                f"LESSON [{result.topic_label}]: {result.lesson_text} "
                f"(quality score {result.score}/10, failure: {result.failure_type})"
            )
            try:
                self._memory.add([
                    {"role": "user", "content": f"[Reflection trigger: {user_input[:200]}]"},
                    {"role": "assistant", "content": lesson_memory},
                ])
                result.lesson_stored = True
            except Exception as e:
                print(f"  [REFLECTION] Memory write failed: {e}")

        # Skill Evolution: Evolve matched skill if execution was flawed or suboptimal
        if matched_skill_ids and result.score <= self._max_fail_score and self._skill_mutator:
            try:
                for target_sid in matched_skill_ids[:2]:
                    rec = self._skill_mutator.evolve_skill(
                        skill_id=target_sid,
                        failure_reason=f"Suboptimal execution (Score {result.score}/10, Failure: {result.failure_type})",
                        user_input=user_input,
                        tool_actions=tool_actions,
                        lesson_text=result.lesson_text,
                    )
                    if rec:
                        result.skill_evolved = True
                        result.evolved_skill_id = rec.skill_id
                        result.new_version = rec.to_version
                        break
            except Exception as e:
                print(f"  [REFLECTION] Skill mutation failed: {e}")

        # Skill Reliability: Record successful execution for matched skills
        if matched_skill_ids and result.score >= 8 and self._skill_mutator:
            try:
                for sid in matched_skill_ids:
                    self._skill_mutator._db.record_success(sid, score=result.score)
            except Exception as e:
                print(f"  [REFLECTION] Skill success record failed: {e}")

        # Auto-write skill if novel success
        if is_novel_success and result.score >= 8:
            try:
                skill_id = self._skill_writer.maybe_write_skill(
                    topic_label=result.topic_label,
                    user_input=user_input,
                    assistant_reply=assistant_reply,
                    score=result.score,
                    skill_matched=skill_matched,
                )
                if skill_id:
                    result.skill_written = True
                    result.skill_id = skill_id
            except Exception as e:
                print(f"  [REFLECTION] Skill write failed: {e}")

        # Trajectory Bank: Record winning multi-step execution traces
        if result.score >= 9 and tool_actions and self._trajectory_mgr:
            try:
                traj_id = self._trajectory_mgr.record_trajectory(
                    user_input=user_input,
                    tool_actions=tool_actions,
                    final_reply=assistant_reply,
                    score=result.score,
                    domain_tag=result.topic_label,
                )
                if traj_id:
                    result.trajectory_id = traj_id
            except Exception as e:
                print(f"  [REFLECTION] Trajectory recording failed: {e}")

        result.duration_ms = int((time.time() - t_start) * 1000)
        return result
