# Changelog

All notable changes to **Ultron Memory Agent** are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).  
Versioning follows [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

---

## [1.3.0] — 2026-09-22

### Added
- **Anti-Fabrication Gate** — grounding validation layer that blocks hallucinated tool outputs before they reach the memory pipeline
- **Task-Adherence Gate** — scope integrity check ensuring agent responses stay within the defined task boundary
- **Scope Integrity Subsystem** — real-time drift detection during multi-step agentic reasoning
- Repository professionalization: GitHub Actions CI, issue/PR templates, `CONTRIBUTING.md`, `SECURITY.md`, `Makefile`, `Dockerfile`
- Organized package structure: `core/`, `memory/`, `reasoning/`, `pipelines/`, `interfaces/`, `infrastructure/`

### Changed
- All root-level Python modules relocated into their respective sub-packages
- Test files moved to `tests/`; fixture data moved to `tests/fixtures/`
- Tax workflow variants archived to `tax_modules/variants/`

---

## [1.2.0] — 2026-09-20

### Added
- **Dual-Core Operational Mode** — `SOLO` (single-agent deep reasoning) and `SWARM` (multi-agent parallel execution) runtime modes
- `langgraph_pipeline.py` cyclic state machine for long-horizon task execution
- `swarm_orchestrator.py` for fan-out multi-agent task distribution
- `chat_session_manager.py` — persistent session identity and context isolation
- `mcp_client.py` — Model Context Protocol client for external tool integration
- `telemetry.py` — structured event tracing and performance metrics
- `critic_gate.py` — in-flight quality gate that intercepts agent outputs before commit
- Phase verification scripts (`verify_phase3` through `verify_phase6`)

### Changed
- `.env.example` extended with SWARM mode configuration parameters

---

## [1.1.0] — 2026-09-10

### Added
- `pyproject.toml` — PEP 517/621 build configuration
- `LICENSE` — MIT License
- Consolidated test suite under `tests/`
- Modularized repository structure with `accounting_modules/`, `tax_modules/`, `scripts/`

---

## [1.0.0] — 2026-09-08

### Added
- **Dual-Phase Memory Pipeline** — Pre-inference semantic retrieval (RRF) + post-inference Mem0 mutation
- **Dynamic Model Router** — Complexity-based routing between fast (Gemini Flash) and deep-reasoning (Claude Sonnet) tiers
- **Tree-of-Thoughts Engine** — Multi-branch reasoning with heuristic evaluation and backtracking
- **Graph RAG Engine** — Entity-relation graph over SQLite + semantic vector indexes
- **Hierarchical Goal Planner** — DAG-based task decomposition and execution tracking
- **ExpeL Trajectory Bank** — Episodic memory of past agentic execution trajectories
- **Execution Ledger Gate** — Budget guardrails with hard spend and token caps
- **Sovereign Killswitch** — Emergency process lockdown with lockfile generation
- **FastAPI Cybernetic Web HUD** — Real-time SSE event stream dashboard at `localhost:8000`
- **Rich Terminal CLI** — Interactive command-line interface with `/memories`, `/forget`, `/clear`
- **Discord Bot Gateway** — Mobile and desktop agent bridge via `discord.py`
- **Email Engine** — Outbound email composition and delivery
- **Sandbox** — Isolated subprocess execution for untrusted tool calls
- Multi-provider LLM support: Gemini, Anthropic Claude, OpenRouter
- Vector store support: ChromaDB (local) + Qdrant (cluster)
- Initial `accounting_modules/` and `tax_modules/` domain packages
