<div align="center">

# ⚡ Ultron Memory Agent

**Enterprise-grade autonomous AI cognitive system with persistent long-term memory,  
multi-model routing, multi-agent swarm orchestration, and governance guardrails.**

[![CI](https://github.com/apparcora-app/ultron-memory-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/apparcora-app/ultron-memory-agent/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://python.org)
[![License: Proprietary](https://img.shields.io/badge/License-Proprietary-red.svg)](LICENSE)
[![Vector Store](https://img.shields.io/badge/Vector%20Store-ChromaDB%20%7C%20Qdrant-green.svg)](https://www.trychroma.com/)
[![Memory Engine](https://img.shields.io/badge/Memory-Mem0-purple.svg)](https://github.com/mem0ai/mem0)
[![Orchestration](https://img.shields.io/badge/Orchestrator-LangGraph%20%7C%20CrewAI-orange.svg)](https://langchain-ai.github.io/langgraph/)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![Changelog](https://img.shields.io/badge/changelog-CHANGELOG.md-blue)](CHANGELOG.md)

</div>

---

## Overview

> **Status: personal use only. Not approved for client data. No approved LLM provider is configured.**

Ultron Memory Agent is a **self-sovereign AI cognitive runtime** designed for high-stakes, long-horizon autonomous tasks. It combines a dual-phase persistent memory pipeline, dynamic complexity-based model routing, Tree-of-Thoughts multi-branch reasoning, and a multi-agent swarm mesh — all governed by hard budget guardrails and an emergency sovereign killswitch.

It ships with three first-class interfaces: a **Rich terminal CLI**, a **FastAPI Cybernetic Web HUD** with real-time SSE streaming, and a **Discord bot gateway**.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                       INTERACTION INTERFACES                        │
│  ┌──────────────────┬──────────────────────┬───────────────────┐   │
│  │  Rich Terminal   │  FastAPI Web HUD      │  Discord Gateway  │   │
│  │    (main.py)     │  (app.py / SSE)       │ (discord_bot.py)  │   │
│  └────────┬─────────┴──────────┬────────────┴────────┬──────────┘   │
└───────────┼────────────────────┼─────────────────────┼─────────────┘
            │                    │                     │
┌───────────▼────────────────────▼─────────────────────▼─────────────┐
│               COGNITIVE CONTROL & REASONING CORE                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Intelligent Model Router (core/model_router.py)             │  │
│  │   Tier 1 Fast:   Gemini Flash / Claude Haiku                 │  │
│  │   Tier 2 Deep:   Gemini Thinking / Claude Sonnet             │  │
│  └────────────────────────────┬─────────────────────────────────┘  │
│  ┌────────────────────────────▼─────────────────────────────────┐  │
│  │  Multi-Agent Orchestration (pipelines/)                      │  │
│  │   • Hierarchical Goal DAG Planner                            │  │
│  │   • Tree-of-Thoughts (ToT) Multi-Branch Evaluator            │  │
│  │   • Graph RAG + ExpeL Episodic Trajectory Memory             │  │
│  │   • LangGraph State Machine & CrewAI Swarm Mesh              │  │
│  └──────────────────────────────────────────────────────────────┘  │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│               DUAL-PHASE MEMORY & PERSISTENCE                       │
│  Phase 1 (Pre-Inference):  Semantic RRF retrieval → context inject  │
│  Phase 2 (Post-Inference): Mem0 fact extraction → ADD/UPDATE/DELETE │
│                                                                     │
│          Local ChromaDB  ←——————————→  Qdrant Cluster              │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│               GOVERNANCE, SAFETY & AUDIT GATES                      │
│  • Budget Guard: hard daily spend (USD) + token caps                │
│  • Sliding-Window Rate Limiter (120 req/min)                        │
│  • Anti-Fabrication Gate + Scope Integrity Check                    │
│  • Sovereign Emergency Killswitch (instant process lockdown)        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Key Features

| Feature | Description |
|---|---|
| **Dual-Phase Memory Pipeline** | Pre-inference semantic retrieval via Reciprocal Rank Fusion (RRF) + post-inference Mem0 mutation (ADD/UPDATE/DELETE) |
| **Dynamic Model Router** | Complexity-based routing between fast (Gemini Flash/Haiku) and deep-reasoning (Sonnet/Gemini Thinking) tiers |
| **Tree-of-Thoughts Engine** | Multi-branch reasoning with heuristic evaluation and backtracking |
| **Graph RAG** | Entity-relation graph in SQLite + semantic vector indexes for relationship traversal |
| **Multi-Agent Swarm** | SOLO mode (single-agent deep reasoning) and SWARM mode (fan-out parallel CrewAI mesh) |
| **Anti-Fabrication Gate** | Grounding validation that blocks hallucinated tool outputs before memory commit |
| **Governance Guardrails** | Hard daily spend limits, sliding-window rate limiter, execution ledger |
| **Sovereign Killswitch** | One-touch emergency process lockdown via `scripts/kill.bat` or `scripts/killswitch.ps1` |
| **Domain Modules** | US GAAP accounting, bookkeeping, payroll, corporate + individual tax workflows |
| **MCP Integration** | Model Context Protocol client for external tool ecosystem connectivity |

---

## Repository Structure

```
ultron-memory-agent/
│
├── core/                         # Agent runtime, model router, tool definitions
├── memory/                       # Dual-phase memory pipeline & vector persistence
├── reasoning/                    # ToT engine, Graph RAG, hierarchical planner, ExpeL
├── pipelines/                    # LangGraph, CrewAI, multi-agent mesh, swarm orchestrator
├── interfaces/                   # (internal) CLI, FastAPI, Discord entrypoints
├── infrastructure/               # MCP client, sandbox, file processor, email, PDF
│
├── governance/                   # Budget tracker, execution ledger gate
├── guardrails/                   # Critic gate, anti-fabrication, artifact verification
├── security/                     # Sovereign killswitch, lockdown
├── resilience/                   # Retry logic, circuit breakers
├── concurrency/                  # Async task management
├── telemetry/                    # Metrics, tracing, event bus
│
├── accounting_modules/           # US GAAP, bookkeeping, payroll, ledger service
├── tax_modules/                  # Corporate & individual tax workflows
│   └── variants/                 # Archived experimental workflow variants
├── agentic-qbo-reconciler/       # QuickBooks Online reconciliation pipeline
├── anti_fabrication_gate/        # Standalone grounding validation subsystem
│
├── skills/                       # Agent skill registry & mutation engine
├── evals/                        # Evaluation benchmarks & golden test sets
├── rules/                        # Operator-defined behavioral rules
├── subsystems/                   # Auxiliary cognitive subsystems
├── utils/                        # Shared utilities
│
├── tests/                        # Automated test suite
│   ├── fixtures/                 # Sample financial data for testing
│   └── conftest.py
├── scripts/                      # Operational launchers & management utilities
│   ├── verify/                   # Phase verification scripts
│   ├── audit_all_systems.py      # Master 5-pillar architectural audit
│   ├── kill.bat                  # Emergency killswitch (CMD)
│   └── killswitch.ps1            # Emergency killswitch (PowerShell)
├── reference_data/               # Authoritative static datasets (US GAAP, SEC tickers)
├── static/                       # Cybernetic Web HUD frontend (HTML/CSS/JS)
├── config/                       # Runtime configuration files
│
├── agent.py                      # ← entry shim (imports core/agent.py)
├── app.py                        # ← entry shim (imports interfaces/app.py)
├── main.py                       # ← entry shim (imports interfaces/main.py)
│
├── Dockerfile                    # Multi-stage Docker image
├── docker-compose.yml            # Compose: Ultron Web HUD + Qdrant
├── Makefile                      # Dev, lint, test, Docker targets
├── pyproject.toml                # PEP 517/621 build config, ruff/mypy/pytest settings
├── requirements.txt              # Production dependency manifest
├── CONTRIBUTING.md               # Developer guide & contribution workflow
├── SECURITY.md                   # Vulnerability reporting policy
├── CHANGELOG.md                  # Version history
├── CODEOWNERS                    # Auto-assign PR reviewers
├── .env.example                  # Sanitized environment template
├── .gitignore                    # Zero-trust secret quarantine rules
└── LICENSE                       # MIT License
```

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/apparcora-app/ultron-memory-agent.git
cd ultron-memory-agent

# 2. Environment
python -m venv .venv
source .venv/bin/activate          # Linux/macOS
# .venv\Scripts\activate           # Windows

pip install -r requirements.txt

# 3. Configure
cp .env.example .env
# Edit .env → add your GEMINI_API_KEY (or ANTHROPIC_API_KEY / OPENROUTER_API_KEY)

# 4. Run
make run-cli    # Interactive Rich terminal CLI
make run-web    # FastAPI Web HUD → http://localhost:8000
```

**Docker (zero-setup):**
```bash
cp .env.example .env   # add your API key
docker-compose up --build -d
# → http://localhost:8000
```

---

## Running the Interfaces

### Interactive Rich CLI
```bash
python main.py
# or
make run-cli
```

CLI slash commands:
| Command | Description |
|---|---|
| `/memories` | Inspect all memories in the vector store |
| `/forget <id>` | Prune a specific memory entry |
| `/clear` | Reset session, retain long-term memories |
| `/quit` | Exit |

### FastAPI Cybernetic Web HUD
```bash
python app.py        # or: make run-web
# Navigate to http://localhost:8000
```

### Discord Bot Gateway
```bash
python discord_bot.py
```

### Launch All Services
```cmd
scripts\start_all.bat
```

---

## Development

```bash
make dev          # install prod + dev deps
make lint         # ruff check
make format       # ruff format (auto-fix)
make typecheck    # mypy (advisory)
make test         # pytest tests/ -v
make test-cov     # tests + coverage report
make audit        # 5-pillar architectural audit
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full developer guide, branch naming conventions, and commit message format.

---

## Testing

```bash
# Full test suite
pytest tests/ -v

# Targeted subsystem verifications
python tests/test_model_routing.py
python tests/test_semantic_search.py
python tests/verify_langchain_pipeline.py
python tests/verify_ledger_integration.py

# Master audit
python scripts/audit_all_systems.py
```

---

## Security

- **Zero Hardcoded Secrets** — All credentials loaded at runtime from `.env` only
- **Local Memory Isolation** — Embeddings default to local disk (`./data/chroma`) — never exfiltrated
- **Anti-Fabrication Gate** — Grounding validation blocks hallucinated outputs before memory commit
- **Emergency Killswitch** — Instant process lockdown: `scripts\kill.bat` or `scripts\killswitch.ps1`

Report vulnerabilities privately — see [SECURITY.md](SECURITY.md).

---

## License

Proprietary — All Rights Reserved. See [LICENSE](LICENSE).

Author: **Hanzla Rehman** ([@apparcora-app](https://github.com/apparcora-app))

---

<div align="center">

[![Star this repo](https://img.shields.io/github/stars/apparcora-app/ultron-memory-agent?style=social)](https://github.com/apparcora-app/ultron-memory-agent/stargazers)
[![Follow](https://img.shields.io/github/followers/apparcora-app?style=social)](https://github.com/apparcora-app)

</div>
