"""
langgraph_pipeline.py — Parallel LangGraph 2-Step Handoff Pipeline (Titan -> Nexus).

Rebuilds the simplest two-step handoff from the Ultron Swarm Orchestrator as a real
LangGraph StateGraph:
  1. Node 'titan': Backend & API architect (produces data models, schema, endpoints).
  2. Node 'nexus': Frontend & UI specialist (consumes Titan's output to build components/client).

Connected via real LangGraph edges (START -> titan -> nexus -> END) with an explicit
TypedDict state schema and full instrumentation wired into TelemetryEngine (SWARM_RUN, AGENT_TASK).
"""

from __future__ import annotations

import os
import re
import time
import uuid
from typing import Any, Callable, List, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from config import LLMConfig
from skill_manager import SkillManager
from swarm_orchestrator import SWARM_SQUAD
from telemetry import TelemetryEngine

# ── 1. Explicit State Schema ──────────────────────────────────────────────────

class SwarmHandoffState(TypedDict):
    """
    Explicit, strongly-typed state schema defining data flow between
    Titan (Backend) and Nexus (Frontend) in the LangGraph execution graph.
    """
    run_id: str
    user_id: str
    directive: str
    context: str

    # Titan Node Outputs (Step 1: Backend / API Architecture)
    titan_task_id: str
    titan_status: str
    titan_output: str
    titan_execution_time_ms: float

    # Nexus Node Outputs (Step 2: Consumes Titan Output -> Frontend UI / Components)
    nexus_task_id: str
    nexus_status: str
    nexus_output: str
    nexus_execution_time_ms: float

    # Pipeline-level Telemetry & Diagnostics
    current_step: str
    errors: List[str]
    total_duration_sec: float


# ── 2. Default LLM Caller Helper ──────────────────────────────────────────────

def _get_default_llm_caller() -> Callable[[str, str], str]:
    """
    Builds a fallback raw LLM caller using Gemini or Claude from the environment.
    """
    cfg = LLMConfig()

    # Try Gemini first if key is present
    if cfg.gemini_api_key:
        try:
            from google import genai
            from google.genai import types as genai_types

            client = genai.Client(api_key=cfg.gemini_api_key)

            def _call_gemini(prompt: str, system_prompt: str) -> str:
                candidates = [
                    cfg.gemini_model,
                    "gemini-flash-latest",
                    "gemini-flash-lite-latest",
                    "gemini-2.5-flash",
                ]
                for model_name in candidates:
                    try:
                        resp = client.models.generate_content(
                            model=model_name,
                            contents=prompt,
                            config=genai_types.GenerateContentConfig(
                                system_instruction=system_prompt if system_prompt else None,
                                temperature=0.2,
                            ),
                        )
                        if resp and resp.text:
                            return resp.text.strip()
                    except Exception:
                        continue
                raise RuntimeError("Gemini model generation failed across candidates.")

            return _call_gemini
        except Exception:
            pass

    # Try Anthropic Claude
    if cfg.anthropic_api_key:
        try:
            import anthropic

            claude_client = anthropic.Anthropic(api_key=cfg.anthropic_api_key)

            def _call_claude(prompt: str, system_prompt: str) -> str:
                resp = claude_client.messages.create(
                    model=cfg.chat_model,
                    max_tokens=4096,
                    system=system_prompt if system_prompt else "You are an expert AI engineer.",
                    messages=[{"role": "user", "content": prompt}],
                )
                if resp.content:
                    return resp.content[0].text.strip()
                return ""

            return _call_claude
        except Exception:
            pass

    # Deterministic Mock Fallback for offline testing
    def _mock_caller(prompt: str, system_prompt: str) -> str:
        if "TITAN" in system_prompt or "Titan" in prompt:
            return (
                "### TITAN BACKEND CONTRACT\n"
                "- Endpoint: `POST /api/v1/telemetry/events`\n"
                "- Schema: `{ event_id: string, user_id: string, event_type: string, duration_ms: number }`\n"
                "- Database: PostgreSQL table `audit_events` with indexed `user_id` and `timestamp`."
            )
        return (
            "### NEXUS FRONTEND IMPLEMENTATION\n"
            "- React Component: `<TelemetryStreamView />` consuming `POST /api/v1/telemetry/events`\n"
            "- Tailwind UI: Titanium glassmorphic table with live event badges and duration formatting."
        )

    return _mock_caller


# ── 3. LangGraph Pipeline Implementation ───────────────────────────────────────

class LangGraphTwoStepSwarm:
    """
    Isolated, parallel LangGraph StateGraph engine implementing the 2-step
    Titan (Backend) -> Nexus (Frontend) handoff with full telemetry logging.
    """

    def __init__(
        self,
        call_llm_fn: Optional[Callable[[str, str], str]] = None,
        telemetry: Optional[TelemetryEngine] = None,
        skill_manager: Optional[SkillManager] = None,
    ) -> None:
        self.call_llm_fn = call_llm_fn or _get_default_llm_caller()
        self.telemetry = telemetry or TelemetryEngine()
        self.skill_manager = skill_manager or SkillManager()
        self.squad = SWARM_SQUAD
        self.graph = self._build_graph()

    def _titan_node(self, state: SwarmHandoffState) -> dict[str, Any]:
        """
        Step 1 Node: Titan (Backend, API & Systems Engineer).
        Generates backend architectures, database schemas, and API contracts.
        """
        t0 = time.time()
        agent_info = self.squad["titan"]
        task_id = f"task_titan_{uuid.uuid4().hex[:6]}"

        skill_context = self.skill_manager.get_skill_context(state["directive"])

        prompt = f"""You are TITAN ({agent_info.role}).
Boss has assigned you the BACKEND / SYSTEMS ARCHITECTURE phase for this directive:
DIRECTIVE: {state["directive"]}
ADDITIONAL CONTEXT: {state.get("context", "")}

APPLICABLE SPECIALIZED SKILL RUNBOOKS:
{skill_context}

Deliver a production-grade backend implementation (FastAPI / Supabase / PostgreSQL schema, endpoints, data types).
Output concrete, clean code and API contracts.
"""
        success = True
        error_msg = None
        output = ""

        try:
            output = self.call_llm_fn(prompt, agent_info.system_prompt)
        except Exception as err:
            output = f"Error in Titan execution: {err}"
            success = False
            error_msg = str(err)

        duration_ms = int((time.time() - t0) * 1000)

        # Wire directly into TelemetryEngine (AGENT_TASK)
        if self.telemetry:
            self.telemetry.log_event(
                user_id=state["user_id"],
                event_type="AGENT_TASK",
                module_id="titan",
                details={
                    "run_id": state["run_id"],
                    "task_id": task_id,
                    "title": "Titan Backend Architecture & API Spec",
                    "agent": "Titan",
                    "engine": "langgraph",
                    "status": "COMPLETED" if success else "ERROR",
                    "success": success,
                    "error": error_msg,
                },
                duration_ms=duration_ms,
            )

        errors = list(state.get("errors", []))
        if not success and error_msg:
            errors.append(f"Titan Node Error: {error_msg}")

        return {
            "titan_task_id": task_id,
            "titan_status": "COMPLETED" if success else "FAILED",
            "titan_output": output,
            "titan_execution_time_ms": float(duration_ms),
            "current_step": "titan",
            "errors": errors,
        }

    def _nexus_node(self, state: SwarmHandoffState) -> dict[str, Any]:
        """
        Step 2 Node: Nexus (Frontend, Mobile UI & Design Specialist).
        Directly consumes Titan's backend output to construct the frontend UI & client.
        """
        t0 = time.time()
        agent_info = self.squad["nexus"]
        task_id = f"task_nexus_{uuid.uuid4().hex[:6]}"

        skill_context = self.skill_manager.get_skill_context(state["directive"])

        # Nexus explicitly consumes Titan's generated contract from graph state
        titan_payload = state.get("titan_output", "No prior backend specification provided.")

        prompt = f"""You are NEXUS ({agent_info.role}).
Boss has assigned you the FRONTEND / UI INTEGRATION phase for this directive:
DIRECTIVE: {state["directive"]}

--- CONSUMED UPSTREAM BACKEND SPECIFICATION FROM TITAN ---
{titan_payload}
---------------------------------------------------------

APPLICABLE SPECIALIZED SKILL RUNBOOKS:
{skill_context}

Deliver modern, accessible React/Next.js components with Tailwind CSS that cleanly consume Titan's API contracts.
Output production-ready UI components and client integration logic.
"""
        success = True
        error_msg = None
        output = ""

        try:
            output = self.call_llm_fn(prompt, agent_info.system_prompt)
        except Exception as err:
            output = f"Error in Nexus execution: {err}"
            success = False
            error_msg = str(err)

        duration_ms = int((time.time() - t0) * 1000)

        # Wire directly into TelemetryEngine (AGENT_TASK)
        if self.telemetry:
            self.telemetry.log_event(
                user_id=state["user_id"],
                event_type="AGENT_TASK",
                module_id="nexus",
                details={
                    "run_id": state["run_id"],
                    "task_id": task_id,
                    "title": "Nexus Frontend UI Component Implementation",
                    "agent": "Nexus",
                    "engine": "langgraph",
                    "consumed_upstream": state.get("titan_task_id", "titan"),
                    "status": "COMPLETED" if success else "ERROR",
                    "success": success,
                    "error": error_msg,
                },
                duration_ms=duration_ms,
            )

        errors = list(state.get("errors", []))
        if not success and error_msg:
            errors.append(f"Nexus Node Error: {error_msg}")

        return {
            "nexus_task_id": task_id,
            "nexus_status": "COMPLETED" if success else "FAILED",
            "nexus_output": output,
            "nexus_execution_time_ms": float(duration_ms),
            "current_step": "nexus",
            "errors": errors,
        }

    def _build_graph(self):
        """
        Assembles and compiles the explicit LangGraph StateGraph:
          START -> 'titan' -> 'nexus' -> END
        """
        builder = StateGraph(SwarmHandoffState)

        # Register actual node functions
        builder.add_node("titan", self._titan_node)
        builder.add_node("nexus", self._nexus_node)

        # Connect with real directed edges
        builder.add_edge(START, "titan")
        builder.add_edge("titan", "nexus")
        builder.add_edge("nexus", END)

        return builder.compile()

    def execute(
        self,
        directive: str,
        context: str = "",
        user_id: str = "boss",
    ) -> SwarmHandoffState:
        """
        Executes the LangGraph 2-step handoff pipeline end-to-end and logs SWARM_RUN telemetry.
        """
        t0 = time.time()
        run_id = f"lg_swarm_{uuid.uuid4().hex[:8]}"

        initial_state: SwarmHandoffState = {
            "run_id": run_id,
            "user_id": user_id,
            "directive": directive,
            "context": context,
            "titan_task_id": "",
            "titan_status": "PENDING",
            "titan_output": "",
            "titan_execution_time_ms": 0.0,
            "nexus_task_id": "",
            "nexus_status": "PENDING",
            "nexus_output": "",
            "nexus_execution_time_ms": 0.0,
            "current_step": "START",
            "errors": [],
            "total_duration_sec": 0.0,
        }

        # Invoke the compiled LangGraph state machine
        final_state: SwarmHandoffState = self.graph.invoke(initial_state)

        total_duration = round(time.time() - t0, 3)
        final_state["total_duration_sec"] = total_duration

        # Wire overall pipeline run into TelemetryEngine (SWARM_RUN)
        if self.telemetry:
            self.telemetry.log_event(
                user_id=user_id,
                event_type="SWARM_RUN",
                module_id="langgraph_pipeline",
                details={
                    "run_id": run_id,
                    "engine": "langgraph",
                    "directive": directive[:200],
                    "subtasks_count": 2,
                    "agents_used": ["titan", "nexus"],
                    "titan_duration_ms": final_state.get("titan_execution_time_ms", 0),
                    "nexus_duration_ms": final_state.get("nexus_execution_time_ms", 0),
                    "total_duration_sec": total_duration,
                    "errors_count": len(final_state.get("errors", [])),
                    "success": len(final_state.get("errors", [])) == 0,
                },
                duration_ms=int(total_duration * 1000),
            )

        return final_state


# ── 4. Standalone CLI Verification Entrypoint ─────────────────────────────────

if __name__ == "__main__":
    import importlib.metadata

    version = importlib.metadata.version("langgraph")
    print(f"\n========================================================")
    print(f"  ULTRON PROTOCOL — LANGGRAPH 2-STEP HANDOFF RUNNER")
    print(f"  Installed LangGraph Version: {version}")
    print(f"========================================================\n")

    pipeline = LangGraphTwoStepSwarm()
    test_directive = "Build an audit log stream endpoint and UI dashboard card."

    print(f"[1/3] Executing LangGraph StateGraph with Directive:")
    print(f"      \"{test_directive}\"\n")

    result = pipeline.execute(directive=test_directive, user_id="boss")

    print(f"[2/3] Execution Complete:")
    print(f"  • Run ID:          {result['run_id']}")
    print(f"  • Titan Status:    {result['titan_status']} ({result['titan_execution_time_ms']}ms)")
    print(f"  • Nexus Status:    {result['nexus_status']} ({result['nexus_execution_time_ms']}ms)")
    print(f"  • Total Duration:  {result['total_duration_sec']}s")
    print(f"  • Errors:          {result['errors'] or 'None'}\n")

    print(f"--- Titan Output (First 200 chars) ---")
    print(f"{result['titan_output'][:200]}...\n")

    print(f"--- Nexus Output (First 200 chars) ---")
    print(f"{result['nexus_output'][:200]}...\n")

    print(f"[3/3] Telemetry Audit Logs:")
    recent = pipeline.telemetry.get_recent_logs(limit=3)
    for log in recent:
        print(f"  • [{log['event_type']}] Module: {log['module_id']}, Duration: {log['duration_ms']}ms, ID: {log['event_id']}")
    print(f"\nLangGraph StateGraph 2-step verification run finished.")
