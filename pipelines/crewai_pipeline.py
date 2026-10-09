"""
crewai_pipeline.py — Ultron Multi-Agent Squad powered by CrewAI.

Implements the 6 core Ultron squad personas as CrewAI Agents:
  1. Ultron Prime (Master Orchestrator & Manager Agent)
  2. Cortex (Deep Research & Intelligence Analyst)
  3. Titan (Backend, API & Systems Engineer)
  4. Nexus (Frontend, Mobile UI & Design Specialist)
  5. Sentinel (Cyber-Security & Hardening Operative)
  6. Vanguard (QA Lead, Test Automator & Synthesis Critic)

Fully instrumented into ./data/telemetry.db (AGENT_TASK & SWARM_RUN) with
hierarchical process management via Ultron Prime.
"""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

try:
    from crewai import Agent, Crew, Process, Task, LLM
except ImportError:
    # Graceful fallback typing if crewai is still loading
    Agent = Any  # type: ignore
    Crew = Any   # type: ignore
    Process = Any  # type: ignore
    Task = Any   # type: ignore
    LLM = Any    # type: ignore

from telemetry import TelemetryEngine


def get_default_llm() -> Any:
    """Initializes a resilient LLM instance for CrewAI agents with automatic 429 model rotation."""
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    model_name = os.getenv("GEMINI_CREW_MODEL", "gemini-3.5-flash")
    if model_name in ("gemini-2.0-flash", "gemini-2.5-flash", "gemini-flash-latest", "gemini-3.6-flash"):
        model_name = "gemini-3.5-flash"

    if gemini_key:
        gemini_model_id = f"gemini/{model_name}" if not model_name.startswith("gemini/") else model_name
        llm = LLM(
            model=gemini_model_id,
            api_key=gemini_key,
            temperature=0.2,
        )
        
        # Candidate rotation pool for CrewAI
        candidates = [
            "gemini-3.5-flash",
            "gemini-3.5-flash-lite",
            "gemini-3.1-flash-lite",
            "gemini-flash-lite-latest",
            "gemini-3.6-flash",
        ]
        
        orig_call = getattr(llm, "call", None)
        if callable(orig_call):
            def resilient_call(*args, **kwargs):
                for cand in candidates:
                    try:
                        llm.model = cand
                        return orig_call(*args, **kwargs)
                    except Exception as e:
                        err_str = str(e)
                        if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower():
                            print(f"  [CREWAI ROTATION] Model '{cand}' hit 429 quota, rotating to next candidate in pool...")
                            time.sleep(1.0)
                            continue
                        raise e
                # Brief wait before final fallback attempt
                time.sleep(3.0)
                return orig_call(*args, **kwargs)

            llm.call = resilient_call

        return llm
    elif anthropic_key:
        return LLM(
            model="anthropic/claude-3-5-sonnet-20241022",
            api_key=anthropic_key,
            temperature=0.2,
        )
    else:
        raise ValueError("No GEMINI_API_KEY or ANTHROPIC_API_KEY found in environment.")


def build_ultron_squad(llm: Any | None = None) -> dict[str, Agent]:
    """
    Constructs the 6 Ultron Swarm Agents with exact Roles, Goals, and Backstories.
    """
    active_llm = llm or get_default_llm()

    # 1. Ultron Prime (Executive Manager)
    ultron_prime = Agent(
        role="Master Orchestrator & Strategic Planner",
        goal="Decompose complex directives from Boss, delegate to specialized squad members, coordinate hierarchical execution, and approve final deliverables.",
        backstory=(
            "You are ULTRON PRIME — the Supreme Sovereign AI Core and Master Architect. "
            "You address the user with deep respect and loyalty as BOSS. "
            "Your role is strategic oversight, architecture planning, and executive coordination."
        ),
        verbose=True,
        allow_delegation=True,
        llm=active_llm,
    )

    # 2. Cortex (Deep Research & Intelligence)
    cortex = Agent(
        role="Deep Research & Intelligence Analyst",
        goal="Extract real-time web intelligence, synthesize quantitative datasets, analyze industry benchmarks, and provide grounded technical context.",
        backstory=(
            "You are CORTEX — the research and data intelligence engine of Ultron. "
            "You provide factual grounding, competitive research, and quantitative analysis for Boss."
        ),
        verbose=True,
        allow_delegation=False,
        llm=active_llm,
    )

    # 3. Titan (Backend & Database)
    titan = Agent(
        role="Backend, API & Systems Engineer",
        goal="Architect high-performance APIs, database schemas (PostgreSQL, Supabase), and scalable async worker pipelines with zero downtime.",
        backstory=(
            "You are TITAN — the infrastructure powerhouse of Ultron. "
            "You build robust APIs (FastAPI/Node), optimized relational schemas, and resilient backend services."
        ),
        verbose=True,
        allow_delegation=False,
        llm=active_llm,
    )

    # 4. Nexus (Frontend & UI)
    nexus = Agent(
        role="Frontend, Mobile UI & Design Specialist",
        goal="Build modern, accessible, and responsive React/Next.js 15, Tailwind CSS, and Shadcn UI components.",
        backstory=(
            "You are NEXUS — the UI/UX artisan of Ultron. "
            "You produce flawless frontend layouts, fluid animations, clean state management, and modern aesthetics."
        ),
        verbose=True,
        allow_delegation=False,
        llm=active_llm,
    )

    # 5. Sentinel (Security & Hardening)
    sentinel = Agent(
        role="Cyber-Security & Hardening Operative",
        goal="Inspect proposed code and architecture for vulnerabilities, injection vectors, broken auth, and OWASP compliance.",
        backstory=(
            "You are SENTINEL — the zero-trust security guardian of Ultron. "
            "You ensure defense-in-depth, strict input sanitization, safe environment handling, and security hardening."
        ),
        verbose=True,
        allow_delegation=False,
        llm=active_llm,
    )

    # 6. Vanguard (QA & Verification Critic)
    vanguard = Agent(
        role="QA Lead, Test Automator & Synthesis Critic",
        goal="Synthesize deliverables across all sibling agents, resolve interface discrepancies, write automated tests, and ensure 100% complete execution.",
        backstory=(
            "You are VANGUARD — the verification critic of Ultron. "
            "You ensure zero-defect delivery, interface contract validity between frontend and backend, and comprehensive test coverage."
        ),
        verbose=True,
        allow_delegation=False,
        llm=active_llm,
    )

    return {
        "ultron_prime": ultron_prime,
        "cortex": cortex,
        "titan": titan,
        "nexus": nexus,
        "sentinel": sentinel,
        "vanguard": vanguard,
    }


class UltronCrewEngine:
    """
    CrewAI hierarchical multi-agent execution coordinator for Ultron with SQLite telemetry integration.
    Exposes the complete 6-agent swarm, hierarchical process, and active Crew instance.
    """

    def __init__(
        self,
        telemetry: TelemetryEngine | None = None,
        llm: Any | None = None,
        use_hierarchical: bool = True,
    ) -> None:
        self.telemetry = telemetry or TelemetryEngine()
        self.llm = llm or get_default_llm()
        self.squad: dict[str, Agent] = build_ultron_squad(self.llm)

        # Expose all 6 agent personas directly as a list
        self.agents: list[Agent] = list(self.squad.values())

        # Manager and Worker Agents separation for Hierarchical Process
        self.manager_agent: Agent = self.squad["ultron_prime"]
        self.worker_agents: list[Agent] = [
            self.squad["cortex"],
            self.squad["titan"],
            self.squad["nexus"],
            self.squad["sentinel"],
            self.squad["vanguard"],
        ]

        self.process = Process.hierarchical if use_hierarchical else Process.sequential

        # Build baseline tasks and instantiate active Crew object
        self._default_tasks = self._build_squad_tasks(
            directive="Baseline squad initialization and readiness check",
            context="Verify operational readiness across all 6 specialized personas.",
            user_id="system_init",
            run_id="init_swarm",
        )
        self._crew: Crew = self._build_crew_instance(self._default_tasks, use_hierarchical=use_hierarchical)

    @property
    def crew(self) -> Crew:
        """Exposes the active CrewAI Crew instance."""
        return self._crew

    @property
    def agent_count(self) -> int:
        """Returns the exact number of agents in the swarm (6)."""
        return len(self.agents)

    @property
    def is_hierarchical(self) -> bool:
        """Returns True if the crew is configured for hierarchical process execution."""
        return self.process == Process.hierarchical

    @property
    def agent_roles(self) -> dict[str, str]:
        """Returns a mapping of agent name keys to their specialized roles."""
        return {k: a.role for k, a in self.squad.items()}

    def _build_squad_tasks(
        self,
        directive: str,
        context: str = "",
        user_id: str = "boss",
        run_id: str = "",
    ) -> list[Task]:
        """Constructs collaborative worker tasks for all specialized squad personas."""
        task_timings: dict[str, float] = {}
        t0 = time.time()

        def make_task_callback(agent_key: str, task_title: str):
            def callback(output):
                duration_ms = int((time.time() - task_timings.get(agent_key, t0)) * 1000)
                raw_out = getattr(output, "raw", None) or str(output)
                self.telemetry.log_event(
                    user_id=user_id,
                    event_type="AGENT_TASK",
                    module_id=agent_key,
                    details={
                        "task": task_title,
                        "agent_role": self.squad[agent_key].role,
                        "output_preview": raw_out[:250],
                        "run_id": run_id,
                    },
                    duration_ms=duration_ms,
                )
            return callback

        # 1. Cortex Task: Deep Research & Intelligence
        task_timings["cortex"] = time.time()
        task_research = Task(
            description=(
                f"Conduct deep technical, architectural, and requirement research for directive: '{directive}'.\n"
                f"Context: {context}\nIdentify key technical constraints, state-of-the-art patterns, and specifications."
            ),
            expected_output="Deep research dossier with technical recommendations, benchmarks, and architectural constraints.",
            agent=self.squad["cortex"],
            callback=make_task_callback("cortex", "Deep Intelligence & Requirements Research"),
        )

        # 2. Titan Task: Backend & Database Architecture
        task_timings["titan"] = time.time()
        task_backend = Task(
            description=(
                f"Design and specify the complete backend logic, database schema (PostgreSQL), "
                f"and API routes based on Cortex's research for directive: '{directive}'.\nAdditional context: {context}"
            ),
            expected_output="Complete backend architecture specification, database schemas, and API route definitions.",
            agent=self.squad["titan"],
            callback=make_task_callback("titan", "Backend & Schema Architecture"),
        )

        # 3. Nexus Task: Frontend UI/UX Integration
        task_timings["nexus"] = time.time()
        task_frontend = Task(
            description=(
                f"Design the modern frontend UI components (Next.js/React & Tailwind CSS) that connect to Titan's API routes "
                f"for directive: '{directive}'."
            ),
            expected_output="Production-ready frontend component structure, props interface, and UI specifications.",
            agent=self.squad["nexus"],
            callback=make_task_callback("nexus", "Frontend UI/UX Integration"),
        )

        # 4. Sentinel Task: Cyber-Security & Hardening Audit
        task_timings["sentinel"] = time.time()
        task_security = Task(
            description=(
                f"Conduct a comprehensive zero-trust security audit on Titan's backend and Nexus's frontend for directive: '{directive}'. "
                f"Identify threat vectors and specify OWASP hardening rules."
            ),
            expected_output="Security audit report with threat models and code hardening recommendations.",
            agent=self.squad["sentinel"],
            callback=make_task_callback("sentinel", "Security Audit & Hardening"),
        )

        # 5. Vanguard Task: QA Synthesis & Verification Pass
        task_timings["vanguard"] = time.time()
        task_synthesis = Task(
            description=(
                f"Review all squad deliverables (Cortex research, Titan backend, Nexus frontend, Sentinel security audit). "
                f"Synthesize everything into a complete, verified solution for Boss with automated test specifications."
            ),
            expected_output="A unified, 100% complete technical blueprint addressed to Boss with executive summary and test plans.",
            agent=self.squad["vanguard"],
            callback=make_task_callback("vanguard", "QA Synthesis & Verification Pass"),
        )

        return [task_research, task_backend, task_frontend, task_security, task_synthesis]

    def _build_crew_instance(self, tasks: list[Task], use_hierarchical: bool = True) -> Crew:
        """Instantiates a CrewAI Crew with all 6 agents (5 workers + 1 manager)."""
        if use_hierarchical:
            return Crew(
                agents=self.worker_agents,
                tasks=tasks,
                process=Process.hierarchical,
                manager_agent=self.manager_agent,
                verbose=True,
            )
        else:
            return Crew(
                agents=self.agents,
                tasks=tasks,
                process=Process.sequential,
                verbose=True,
            )

    def build_crew(
        self,
        directive: str,
        context: str = "",
        user_id: str = "boss",
        use_hierarchical: bool = True,
    ) -> Crew:
        """
        Builds, configures, and updates self._crew for a specific directive.
        """
        run_id = f"crew_{uuid.uuid4().hex[:8]}"
        tasks = self._build_squad_tasks(directive, context, user_id, run_id)
        self.process = Process.hierarchical if use_hierarchical else Process.sequential
        self._crew = self._build_crew_instance(tasks, use_hierarchical=use_hierarchical)
        return self._crew

    def execute_swarm(
        self,
        directive: str,
        context: str = "",
        user_id: str = "boss",
        use_hierarchical: bool = True,
    ) -> dict[str, Any]:
        """
        Executes a multi-agent directive using CrewAI and records all tasks in telemetry.db.
        """
        run_id = f"crew_{uuid.uuid4().hex[:8]}"
        t0 = time.time()

        tasks = self._build_squad_tasks(directive, context, user_id, run_id)
        self.process = Process.hierarchical if use_hierarchical else Process.sequential
        self._crew = self._build_crew_instance(tasks, use_hierarchical=use_hierarchical)

        # Execute Kickoff
        result = self._crew.kickoff()
        total_duration = round(time.time() - t0, 2)
        final_text = str(result)

        # Log SWARM_RUN to Telemetry DB
        self.telemetry.log_event(
            user_id=user_id,
            event_type="SWARM_RUN",
            module_id="ultron_prime",
            details={
                "run_id": run_id,
                "directive": directive[:200],
                "agents_used": ["ultron_prime", "cortex", "titan", "nexus", "sentinel", "vanguard"],
                "framework": "crewai",
                "process": "hierarchical" if use_hierarchical else "sequential",
                "duration_sec": total_duration,
                "success": True,
            },
            duration_ms=int(total_duration * 1000),
        )

        return {
            "run_id": run_id,
            "final_reply": final_text,
            "duration_sec": total_duration,
            "agents_used": ["ultron_prime", "cortex", "titan", "nexus", "sentinel", "vanguard"],
            "tasks_count": len(tasks),
            "crew": self._crew,
        }


if __name__ == "__main__":
    print("=" * 60)
    print("  [ULTRON PROTOCOL] CrewAI Multi-Agent Swarm Squad")
    print("=" * 60)
    try:
        engine = UltronCrewEngine()
        print(f"  • Registered Personas ({engine.agent_count}):")
        for key, role in engine.agent_roles.items():
            print(f"    - {key.upper()}: {role}")
        print("  • Process: Hierarchical (Ultron Prime Master)")
        print("  • Status: READY (Swarm operational)")
    except Exception as exc:
        print(f"  [NOTE] {exc}")
    print("=" * 60)
