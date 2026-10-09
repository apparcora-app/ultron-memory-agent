# Changelog

All notable changes to **Ultron Memory Agent** are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).  
Versioning follows [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

### Added
- **Manual Test Isolation**: Created `tests/manual/` containing 34 manual, integration, and high-risk exploratory test scripts with automatic repo root path insertion, accompanied by a comprehensive `README.md`.
- **Live-LLM Test Tagging**: Registered `@pytest.mark.llm_live` marker for live LLM evals (`tests/evals/test_agent_hallucination.py`), isolating them from standard CI runs via `addopts = "-v --tb=short -m 'not llm_live'"`.
- **Automated Scratch Relocation**: Quarantined 128 scratch, output, and iteration files from the repository root into `../ultron-scratch` with full `MANIFEST.csv` and automated `restore.ps1`.

### Changed
- **Killswitch Fail-Closed Hardening**: Hardened `security/killswitch.py` to completely eliminate hardcoded fallback secrets (`ULTRON-TERMINATE-ALPHA-99`, `ULTRON-OVERRIDE-BOSS-77`) and fail closed if `KILLSWITCH_SECRET_KEY` / `KILLSWITCH_OVERRIDE_CODE` is missing or empty.
- **Pytest Multi-Layer Exclusion**: Configured `norecursedirs = ["tests/manual"]` in `pyproject.toml` and `collect_ignore_glob = ["manual/*"]` in `tests/conftest.py` ensuring zero accidental collection of manual test scripts.
- **Accepted Risks Documentation**: Updated `SECURITY.md` documenting accepted architectural risks for local D-drive backups, un-reaped crash processes, and personal-mode Mem0 retention.
- **Fine-Grained Retention Lifecycle**: Updated `pii_cleanup.py` and `core/config.py` with granular retention settings: `SESSIONS_RETENTION_DAYS=90`, `TELEMETRY_RETENTION_DAYS=90`, `AUDIT_LOG_RETENTION_DAYS=365`, `BLACKBOARD_RETENTION_DAYS=30`, and `PURGE_MEM0=false`.
- **Mem0 Retention Policy**: Set `PURGE_MEM0=false` by default to preserve personal memory while only personal data is stored; documented client onboarding requirement to enable Mem0 purging before client data ingestion.
- **Enhanced PII Dry-Run Inspection**: `--dry-run` now logs active settings in use, counts, and the first 5 sample IDs/filenames per category that would be purged without mutating storage.

- **Security**: Pinned dependencies into a reproducible \
equirements.lock\ using \pip-compile\.
- **Security**: Integrated \pip-audit\ into \scripts/audit_deps.sh\ to scan and enforce zero known vulnerabilities.
- **Security**: Upgraded vulnerable versions of \iohttp\, \astapi\, \
equests\, \urllib3\, and \uvicorn\.

### Added
- **Incident Response Plan**: Created \docs/INCIDENT_RESPONSE.md\ to provide strict, checklist-style procedures for PII exposure and harmful agent actions.
- **Automated PII Retention Purge**: Added retention-based cleanup across 	elemetry.db, computer_audit.jsonl, data/sessions/, data/blackboard/, and Mem0/Chroma entries (configured via pii_retention_days). Includes a --dry-run mode.
- **Task Scheduler PII Purge Automation**: Added scripts/schedule_pii_purge.ps1 to easily schedule the retention script.
- **Automated Off-Machine Backup**: Added scripts/backup.py and scripts/restore.py to encrypt (AES-128 via Fernet) and upload core state (ChromaDB, config, databases, logs) to configurable cold storage (via 
clone). Excludes .env. Enforces 7-daily + 4-weekly retention policy.
- **Task Scheduler Backup Automation**: Added scripts/schedule_backup.ps1 for easy deployment of the backup lifecycle job.
- **API Key Authentication**: X-API-Key header required on all endpoints (except /health). Keys are securely hashed in memory via hmac.compare_digest.
- **Per-Key Governance**: 
ate_limiter.py and spend_governor.py now attribute API quotas and financial budgets to the hashed caller ID, enabling multi-tenant rate isolation.
- **Human-in-the-Loop (HITL) Approval Gate**: Required for irreversible actions (
un_python, execute_command, file deletion/overwrites, outbound messages, DB memory writes). Blocks execution on timeout or explicit denial, ensuring safe autonomous runs.

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
