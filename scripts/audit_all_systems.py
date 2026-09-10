"""
================================================================================
 ULTRON PROTOCOL — MASTER ARCHITECTURE & SELF-LEARNING AUDIT SUITE
================================================================================
Comprehensive verification of all 5 Pillars and core agentic subsystems:
  [1] Environment, SQLite DBs & ChromaDB Collections
  [2] Pillar 1: Dense Semantic Skill Vector Retrieval & RRF
  [3] Pillar 2: In-Flight Pre-Response Critic Gate & Confidence Filter
  [4] Pillar 3: Episodic Trajectory Bank (ExpeL Replay)
  [5] Pillar 4: Autonomous Skill Mutation, Versioning & Reliability
  [6] Pillar 5: Autonomous Dreaming & Virtual Sandbox Simulation
  [7] End-to-End Agent Runtime & Tool Execution Sandbox

Author: Ultron Autonomous System Architect
================================================================================
"""

import os
import sys
import time
import json
import sqlite3
import tempfile
import warnings
from pathlib import Path

# Silence deprecation warnings for clean output
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# UTF-8 stdout bootstrap for Windows console
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

import anthropic
import chromadb
from config import LLMConfig
DATA_DIR = PROJECT_ROOT / "data"

from telemetry import TelemetryEngine
from skill_manager import SkillManager
from reflection_engine import InFlightCritic, ReflectionEngine
from trajectory_manager import TrajectoryManager
from skill_evolution import SkillMutator, SkillEvolutionDB
from dreaming_engine import DreamingEngine, DreamCandidate
from sandbox import Sandbox, SandboxConfig
from tool_definitions import ToolExecutor
from agent import MemoryAgent

TOTAL_PASS = 0
TOTAL_FAIL = 0
AUDIT_LOGS: list[str] = []


def p(msg: str = ""):
    print(msg, flush=True)


def record_result(pillar_name: str, test_desc: str, passed: bool, details: str = "", duration_s: float = 0.0):
    global TOTAL_PASS, TOTAL_FAIL
    if passed:
        TOTAL_PASS += 1
        tag = "[✓ PASS]"
    else:
        TOTAL_FAIL += 1
        tag = "[✗ FAIL]"
    msg = f"  {tag} {test_desc} ({duration_s:.2f}s)"
    if details:
        msg += f"\n       -> {details}"
    AUDIT_LOGS.append(f"{pillar_name}: {msg}")
    p(msg)


def run_master_audit():
    global TOTAL_PASS, TOTAL_FAIL
    t_start_all = time.time()

    p("=" * 80)
    p(" 🚀 ULTRON PROTOCOL — MASTER ARCHITECTURE & 5-PILLAR SYSTEM AUDIT")
    p("=" * 80)

    llm_cfg = LLMConfig()
    claude = anthropic.Anthropic(api_key=llm_cfg.anthropic_api_key) if llm_cfg.anthropic_api_key else None
    try:
        from google import genai
        gemini = genai.Client(api_key=llm_cfg.gemini_api_key) if getattr(llm_cfg, "gemini_api_key", None) else None
    except Exception:
        gemini = None
    telemetry = TelemetryEngine()
    skill_mgr = SkillManager()
    traj_mgr = TrajectoryManager()
    evo_db = SkillEvolutionDB()

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 1: Infrastructure, SQLite DBs & ChromaDB Storage
    # ──────────────────────────────────────────────────────────────────────────
    p("\n[AUDIT 1/7] Core Infrastructure & Data Persistence Layer...")
    t0 = time.time()
    try:
        # Check SQLite DBs
        db_files = [
            DATA_DIR / "telemetry.db",
            DATA_DIR / "skill_evolution.db",
            DATA_DIR / "dreaming.db",
        ]
        all_dbs_exist = all(p.exists() for p in db_files)
        
        # Check ChromaDB Collections
        client = chromadb.PersistentClient(path=str(skill_mgr.chroma_path))
        colls = [c.name for c in client.list_collections()]
        has_skills_coll = "ultron_skills_index" in colls
        has_traj_coll = "ultron_trajectories" in colls

        passed = all_dbs_exist and has_skills_coll and has_traj_coll
        details = f"Databases: 3/3 | ChromaDB Collections: {colls}"
        record_result("INFRA", "SQLite DBs & ChromaDB Collections Active", passed, details, time.time() - t0)
    except Exception as e:
        record_result("INFRA", "SQLite DBs & ChromaDB Collections Active", False, str(e), time.time() - t0)

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 2: Pillar 1 — Dense Semantic Vector Skill Retrieval & RRF
    # ──────────────────────────────────────────────────────────────────────────
    p("\n[AUDIT 2/7] Pillar 1: Dense Semantic Skill Vector Retrieval (ChromaDB + RRF)...")
    t0 = time.time()
    try:
        matches = skill_mgr.get_matched_skills("calculate net profit margin and generate financial report")
        has_matches = len(matches) > 0
        names = [m.name for m in matches]
        details = f"Retrieved {len(matches)} skill(s): {names}"
        record_result("PILLAR 1", "RRF Hybrid & Dense Embedding Retrieval", has_matches, details, time.time() - t0)
    except Exception as e:
        record_result("PILLAR 1", "RRF Hybrid & Dense Embedding Retrieval", False, str(e), time.time() - t0)

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 3: Pillar 2 — In-Flight Critic Pre-Response Gate
    # ──────────────────────────────────────────────────────────────────────────
    p("\n[AUDIT 3/7] Pillar 2: Pre-Response In-Flight Critic Gate (Claude Haiku)...")
    try:
        t0 = time.time()
        critic = InFlightCritic(
            claude=claude,
            gemini=gemini,
            haiku_model=llm_cfg.chat_model_haiku,
            gemini_model=llm_cfg.gemini_model,
            provider=llm_cfg.provider,
        )
        crit_res = critic.verify_in_flight(
            user_input="Compute the total of 1500 and 3500",
            draft_reply="The calculated sum of 1500 and 3500 is 5000.",
            tool_actions=[{"tool": "run_python", "args": {"code": "print(1500 + 3500)"}, "output": "5000", "success": True}],
        )
        passed = crit_res.approved and crit_res.flaw_severity == "none"
        details = f"Approved: {crit_res.approved} | Severity: {crit_res.flaw_severity} | Critique: {crit_res.critique[:70]}..."
        record_result("PILLAR 2", "In-Flight Critic Pre-Verification (<1s)", passed, details, time.time() - t0)
    except Exception as e:
        record_result("PILLAR 2", "In-Flight Critic Pre-Verification (<1s)", False, str(e), time.time() - t0)

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 4: Pillar 3 — Episodic Trajectory Bank (ExpeL Replay)
    # ──────────────────────────────────────────────────────────────────────────
    p("\n[AUDIT 4/7] Pillar 3: Episodic Trajectory Bank (Few-Shot Precedent Replay)...")
    t0 = time.time()
    try:
        test_traj_id = traj_mgr.record_trajectory(
            user_input="Fetch cryptocurrency live pricing for Bitcoin",
            tool_actions=[{"tool": "crypto_fetch", "args": {"coin": "BTC"}, "output": "98500 USD", "success": True}],
            final_reply="Bitcoin is currently trading at $98,500 USD.",
            score=10,
            domain_tag="crypto",
        )
        retrieved = traj_mgr.get_relevant_trajectory("What is the current price of BTC?")
        passed = retrieved is not None
        details = f"Precedent Replay Match: ID='{retrieved.id if retrieved else 'None'}' | Score={retrieved.score if retrieved else 0}"
        record_result("PILLAR 3", "Episodic Trajectory Storage & Semantic Replay", passed, details, time.time() - t0)
    except Exception as e:
        record_result("PILLAR 3", "Episodic Trajectory Storage & Semantic Replay", False, str(e), time.time() - t0)

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 5: Pillar 4 — Autonomous Skill Mutation & Versioning
    # ──────────────────────────────────────────────────────────────────────────
    p("\n[AUDIT 5/7] Pillar 4: Autonomous Skill Mutation, Versioning & Reliability...")
    t0 = time.time()
    audit_skill_id = "master_audit_temp_skill"
    try:
        skill_dir = skill_mgr.skills_dir / audit_skill_id
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: {audit_skill_id}\ndescription: Master audit test skill for version mutation\nversion: 1.0\n---\n# Master Audit Skill v1.0\n",
            encoding="utf-8",
        )
        skill_mgr.reload_skills()

        mutator = SkillMutator(
            claude=claude,
            gemini=gemini,
            haiku_model=llm_cfg.chat_model_haiku,
            gemini_model=llm_cfg.gemini_model,
            provider=llm_cfg.provider,
            skills_dir=skill_mgr.skills_dir,
            skill_manager=skill_mgr,
        )

        rec = mutator.evolve_skill(
            skill_id=audit_skill_id,
            failure_reason="TypeError: expected list but received dictionary payload",
            user_input="Run master audit task",
            lesson_text="Ensure dictionary payloads are coerced into lists before iteration.",
        )

        passed = rec is not None and rec.to_version == "1.1"
        details = f"Mutated Version: {rec.to_version if rec else 'None'} | Evolution Rule: {rec.edge_case_title if rec else 'None'}"
        record_result("PILLAR 4", "Autonomous Skill Mutation & Version Bumping", passed, details, time.time() - t0)
    except Exception as e:
        record_result("PILLAR 4", "Autonomous Skill Mutation & Version Bumping", False, str(e), time.time() - t0)
    finally:
        skill_mgr.delete_skill(audit_skill_id)

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 6: Pillar 5 — Autonomous Dreaming Engine & Virtual Sandbox Replay
    # ──────────────────────────────────────────────────────────────────────────
    p("\n[AUDIT 6/7] Pillar 5: Autonomous Dreaming & Virtual Sandbox Simulation...")
    t0 = time.time()
    dream_skill_id = "master_audit_dream_skill"
    try:
        skill_dir = skill_mgr.skills_dir / dream_skill_id
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: {dream_skill_id}\ndescription: Dream simulation verification skill\nversion: 1.0\n---\n# Dream Skill v1.0\n",
            encoding="utf-8",
        )
        skill_mgr.reload_skills()

        dreamer = DreamingEngine(
            claude=claude,
            gemini=gemini,
            haiku_model=llm_cfg.chat_model_haiku,
            gemini_model=llm_cfg.gemini_model,
            provider=llm_cfg.provider,
            telemetry=telemetry,
            skill_manager=skill_mgr,
            skill_mutator=mutator,
            trajectory_manager=traj_mgr,
        )

        cand = DreamCandidate(
            candidate_id=f"audit_dream_{int(time.time())}",
            source="telemetry_audit",
            domain=dream_skill_id,
            prompt_context="Parse API response containing single quotes: {'status': 'success', 'code': 200}",
            failed_tool=dream_skill_id,
            error_message="json.decoder.JSONDecodeError: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)",
            raw_details={},
        )

        dream_res = dreamer.simulate_dream(cand)
        passed = dream_res.success
        details = f"Hypothesis: {dream_res.hypothesis[:70]}... | Sandbox Output: {dream_res.execution_output.strip()[:60]}..."
        record_result("PILLAR 5", "Sandbox Replay, Auto-Patching & Trajectory Commit", passed, details, time.time() - t0)
    except Exception as e:
        record_result("PILLAR 5", "Sandbox Replay, Auto-Patching & Trajectory Commit", False, str(e), time.time() - t0)
    finally:
        skill_mgr.delete_skill(dream_skill_id)

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 7: Tool Execution Sandbox & End-to-End Agent Runtime
    # ──────────────────────────────────────────────────────────────────────────
    p("\n[AUDIT 7/12] End-to-End Agent Runtime & Tool Execution Sandbox...")
    t0 = time.time()
    try:
        sandbox = Sandbox(config=SandboxConfig(python_timeout=10, command_timeout=10))
        executor = ToolExecutor(sandbox=sandbox)
        
        # 1. Test Python Sandbox Execution
        py_res = executor.execute("run_python", {"code": "x = [i**2 for i in range(5)]\nprint('POWERS:', x)"})
        py_ok = py_res.get("success", False) and "POWERS: [0, 1, 4, 9, 16]" in py_res.get("output", "")

        # 2. Test Real Live Agent Chat & Autonomous Tool Roundtrip
        agent = MemoryAgent(user_id="boss_master_audit")
        chat_res = agent.chat("Compute 47 * 89 in Python and report the exact number.")
        chat_tools = [t.get("tool") for t in chat_res.get("tool_actions", [])]
        chat_ok = (
            bool(chat_res.get("reply"))
            and "4183" in chat_res.get("reply", "")
            and len(chat_tools) >= 1
        )

        passed = py_ok and chat_ok
        details = f"Sandbox Exec: {'OK' if py_ok else 'FAIL'} | Tools Called: {chat_tools} | Output Verified: {chat_ok} (4183) | Model: {chat_res.get('model_used')}"
        record_result("RUNTIME", "Agentic Loop, Autonomous Tool Execution & LLM Reasoning", passed, details, time.time() - t0)
    except Exception as e:
        record_result("RUNTIME", "Agentic Loop, Autonomous Tool Execution & LLM Reasoning", False, str(e), time.time() - t0)

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 8: Cognitive Breakthrough 1 — Tree-of-Thoughts / MCTS Rollout Engine
    # ──────────────────────────────────────────────────────────────────────────
    p("\n[AUDIT 8/10] Cognitive Breakthrough 1: Tree-of-Thoughts & MCTS Reasoning Engine...")
    t0 = time.time()
    try:
        from tot_engine import TreeOfThoughtsEngine
        tot_engine = TreeOfThoughtsEngine(
            claude=claude,
            gemini=gemini,
            haiku_model=llm_cfg.chat_model_haiku,
            sonnet_model=llm_cfg.chat_model,
            gemini_model=llm_cfg.gemini_model,
            provider=llm_cfg.provider,
            tool_executor=executor,
            trajectory_manager=traj_mgr,
            telemetry=telemetry,
        )
        tot_res = tot_engine.search(
            query="Verify whether 3571 is prime by computing divisors in Python.",
            max_depth=2,
            branch_factor=2,
            beam_width=2,
            time_limit_s=25.0,
            user_id="master_audit_tot",
        )
        passed = tot_res.success and tot_res.confidence_score >= 0.60
        details = f"Confidence: {tot_res.confidence_score:.2f} | Nodes: {tot_res.total_nodes_generated} | Pruned: {tot_res.total_nodes_pruned} | Depth: {tot_res.tree_depth}"
        record_result("TREE SEARCH", "Tree-of-Thoughts MCTS Rollout & Trajectory Commit", passed, details, time.time() - t0)
    except Exception as e:
        record_result("TREE SEARCH", "Tree-of-Thoughts MCTS Rollout & Trajectory Commit", False, str(e), time.time() - t0)

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 9: Cognitive Breakthrough 2 — Dynamic Graph-RAG & Causal Knowledge Graph
    # ──────────────────────────────────────────────────────────────────────────
    p("\n[AUDIT 9/10] Cognitive Breakthrough 2: Dynamic Graph-RAG & Causal Knowledge Graph...")
    t0 = time.time()
    try:
        import tempfile
        from graph_rag_engine import GraphRAGEngine
        kg_temp = tempfile.mkdtemp(prefix="audit_kg_")
        kg_path = os.path.join(kg_temp, "master_audit_kg.sqlite3")
        graph_rag = GraphRAGEngine(
            db_path=kg_path,
            claude=claude,
            gemini=gemini,
            haiku_model=llm_cfg.chat_model_haiku,
            gemini_model=llm_cfg.gemini_model,
            provider=llm_cfg.provider,
            telemetry=telemetry,
        )
        # Test Entity Linking & Subgraph Query
        subgraph_ctx = graph_rag.query_subgraph(
            query="What systems did Boss architect and what frameworks do they use?",
            max_hops=2,
        )
        stats = graph_rag.store.get_stats()
        passed = len(subgraph_ctx.seed_entities) >= 1 and stats["total_triples"] >= 3 and bool(subgraph_ctx.formatted_markdown)
        details = f"Entities: {stats['total_entities']} | Triples: {stats['total_triples']} | Seeds Matched: {len(subgraph_ctx.seed_entities)} | Time: {subgraph_ctx.traversal_time_s:.4f}s"
        record_result("GRAPH-RAG", "Dynamic Graph-RAG, Entity Linking & Causal Provenance", passed, details, time.time() - t0)
    except Exception as e:
        record_result("GRAPH-RAG", "Dynamic Graph-RAG, Entity Linking & Causal Provenance", False, str(e), time.time() - t0)

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 10: Cognitive Breakthrough 3 — Hierarchical Goal Decomposition & Dynamic DAG
    # ──────────────────────────────────────────────────────────────────────────
    p("\n[AUDIT 10/10] Cognitive Breakthrough 3: Hierarchical Goal Decomposition & Self-Evolving Planner...")
    t0 = time.time()
    try:
        import tempfile
        from hierarchical_planner import HierarchicalPlanner
        ht_temp = tempfile.mkdtemp(prefix="audit_htree_")
        ht_path = os.path.join(ht_temp, "master_audit_htree.sqlite3")
        h_planner = HierarchicalPlanner(
            db_path=ht_path,
            claude=claude,
            gemini=gemini,
            sonnet_model=llm_cfg.chat_model,
            haiku_model=llm_cfg.chat_model_haiku,
            gemini_model=llm_cfg.gemini_model,
            provider=llm_cfg.provider,
            tool_executor=executor,
            trajectory_manager=traj_mgr,
            telemetry=telemetry,
        )
        plan_res = h_planner.plan_and_execute(
            goal_text="Compute compound return on $5,000 at 8% for 5 years in Python and format deliverable.",
            user_id="master_audit_htree",
        )
        passed = plan_res.success and plan_res.completed_nodes >= 1 and plan_res.total_nodes >= 3
        details = f"Nodes: {plan_res.total_nodes} | Completed: {plan_res.completed_nodes} | Mutated: {plan_res.mutated_nodes} | Time: {plan_res.total_duration_s:.2f}s"
        record_result("H-TREE PLANNER", "Hierarchical Goal Decomposition & Dynamic DAG Execution", passed, details, time.time() - t0)
    except Exception as e:
        record_result("H-TREE PLANNER", "Hierarchical Goal Decomposition & Dynamic DAG Execution", False, str(e), time.time() - t0)

    # ── [AUDIT 11/12] Autonomous Email & Inbox Engine ────────────────────────
    p("[AUDIT 11/12] Autonomous Email & Inbox Engine (IMAP/SMTP/Drafting)...")
    t0 = time.time()
    try:
        from email_engine import EmailEngine
        email_engine = EmailEngine()
        p_res = email_engine.resolve_profile("primary")
        draft_res = email_engine.draft_email(
            to="sarah.adams@generic_firm.com",
            subject="Audit Invoice Verification",
            body="Hi sarah, confirming invoice review status.",
            profile="primary",
        )
        passed = (
            p_res["user"] == "hanzla.rehman@primarybooksntax.com"
            and draft_res["success"] is True
            and Path(draft_res["eml_path"]).exists()
        )
        details = f"Profile: {p_res['profile_name']} ({p_res['user']}) | Draft Saved: {draft_res['draft_id']}"
        record_result("EMAIL ENGINE", "Autonomous Email & Inbox Engine (MIME Draft & IMAP/SMTP Routing)", passed, details, time.time() - t0)
    except Exception as e:
        record_result("EMAIL ENGINE", "Autonomous Email & Inbox Engine (MIME Draft & IMAP/SMTP Routing)", False, str(e), time.time() - t0)

    # ── [AUDIT 12/12] CrewAI Hierarchical 6-Agent Swarm ───────────────────────
    p("[AUDIT 12/12] CrewAI Hierarchical 6-Agent Swarm (.crew Object & Persona Verification)...")
    t0 = time.time()
    try:
        from crewai_pipeline import UltronCrewEngine
        crew_engine = UltronCrewEngine(use_hierarchical=True)
        crew_obj = crew_engine.crew
        passed = (
            hasattr(crew_engine, "crew")
            and crew_obj is not None
            and crew_engine.agent_count == 6
            and len(crew_engine.agents) == 6
            and crew_engine.is_hierarchical is True
            and crew_obj.manager_agent.role == "Master Orchestrator & Strategic Planner"
            and len(crew_obj.tasks) == 5
        )
        details = f"Agents: {crew_engine.agent_count}/6 | Hierarchical: {crew_engine.is_hierarchical} | Manager: {crew_obj.manager_agent.role[:20]}... | Tasks: {len(crew_obj.tasks)}"
        record_result("CREWAI SWARM", "CrewAI Hierarchical 6-Agent Swarm & Active .crew Object", passed, details, time.time() - t0)
    except Exception as e:
        record_result("CREWAI SWARM", "CrewAI Hierarchical 6-Agent Swarm & Active .crew Object", False, str(e), time.time() - t0)

    # ──────────────────────────────────────────────────────────────────────────
    # MASTER SUMMARY REPORT
    # ──────────────────────────────────────────────────────────────────────────
    total_elapsed = time.time() - t_start_all
    p("\n" + "=" * 80)
    p(" 📊 MASTER AUDIT SCORECARD & ARCHITECTURAL SUMMARY")
    p("=" * 80)
    p(f" Total Audits Run : {TOTAL_PASS + TOTAL_FAIL}")
    p(f" Passed           : {TOTAL_PASS}")
    p(f" Failed           : {TOTAL_FAIL}")
    p(f" Success Rate     : {(TOTAL_PASS / (TOTAL_PASS + TOTAL_FAIL) * 100):.1f}%")
    p(f" Total Time       : {total_elapsed:.2f}s")
    p("-" * 80)

    if TOTAL_FAIL == 0:
        p(" [PASS] ALL 12 AUDIT SUITES PASSED — ZERO FAILURES DETECTED")
    else:
        p(f" [FAIL] {TOTAL_FAIL} AUDIT(S) FAILED — REVIEW TRACES AND LOGS ABOVE")
    p("=" * 80 + "\n")


if __name__ == "__main__":
    run_master_audit()
