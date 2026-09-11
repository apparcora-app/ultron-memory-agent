# 🧠 Ultron Memory Agent

[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Vector Store](https://img.shields.io/badge/Vector%20Store-ChromaDB%20%7C%20Qdrant-green.svg)](https://www.trychroma.com/)
[![Memory Engine](https://img.shields.io/badge/Memory-Mem0-purple.svg)](https://github.com/mem0ai/mem0)
[![Orchestration](https://img.shields.io/badge/Orchestrator-LangGraph%20%7C%20CrewAI-orange.svg)](https://langchain-ai.github.io/langgraph/)
[![Framework](https://img.shields.io/badge/Framework-FastAPI%20%7C%20Discord.py-red.svg)](https://fastapi.tiangolo.com/)

> **Ultron Memory Agent** is an enterprise-grade autonomous AI cognitive system featuring persistent long-term memory, dynamic multi-model complexity routing, Tree-of-Thoughts (ToT) exploration, multi-agent swarm orchestration, and an emergency sovereign killswitch.

---

## 🏛️ System Architecture

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                            INTERACTION INTERFACES                           │
│     ┌──────────────────────┬──────────────────────┬───────────────────┐     │
│     │   Rich Terminal CLI  │  Cybernetic Web HUD  │  Discord Gateway  │     │
│     │      (main.py)       │    (FastAPI / SSE)   │  (discord_bot.py) │     │
│     └──────────┬───────────┴──────────┬───────────┴─────────┬─────────┘     │
└────────────────┼──────────────────────┼─────────────────────┼───────────────┘
                 │                      │                     │
┌────────────────▼──────────────────────▼─────────────────────▼───────────────┐
│                    COGNITIVE CONTROL & REASONING CORE                       │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                     Intelligent Model Router                          │  │
│  │   • Tier 1 Fast / Daily (Gemini 3.8 Flash / Haiku 4.5)                │  │
│  │   • Tier 2 Deep Reasoning (Gemini Thinking / Claude 3.5 Sonnet)       │  │
│  └──────────────────────────────────┬────────────────────────────────────┘  │
│                                     │                                       │
│  ┌──────────────────────────────────▼────────────────────────────────────┐  │
│  │                    Multi-Agent Orchestration Mesh                     │  │
│  │   • Hierarchical Planner & Goal DAG Manager                           │  │
│  │   • Tree-of-Thoughts (ToT) Multi-Branch Evaluation Engine             │  │
│  │   • Graph RAG & Episodic Trajectory Memory (ExpeL)                    │  │
│  │   • LangGraph Cyclic State Machine & CrewAI Multi-Agent Swarms        │  │
│  └──────────────────────────────────┬────────────────────────────────────┘  │
└─────────────────────────────────────┼───────────────────────────────────────┘
                                      │
┌─────────────────────────────────────▼───────────────────────────────────────┐
│                     TWO-PHASE MEMORY & PERSISTENCE                          │
│                                                                             │
│   Phase 1 (Pre-Inference): Semantic Retrieval & Reciprocal Rank Fusion (RRF)│
│                            Relevant memories injected into Context Window   │
│                                                                             │
│   Phase 2 (Post-Inference): Fact Extraction & Conflict Resolution (Mem0)    │
│                            ADD / UPDATE / DELETE applied to Vector Store    │
│                                                                             │
│            Vector Databases: Local ChromaDB  <───>  Qdrant Cluster          │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
┌─────────────────────────────────────▼───────────────────────────────────────┐
│                      GOVERNANCE, SAFETY & AUDIT GATES                       │
│   • Execution Ledger Gate & Budget Guard (Hard Spend / Token Caps)          │
│   • Sliding-Window Rate Limiter & In-Flight Critic Gate                     │
│   • Sovereign Emergency Killswitch (Fast-Halt Process Lockdown)             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## ⚡ Technical Deep-Dives

### 1. Dual-Phase Memory Pipeline (Mem0 + Hybrid RRF)
* **Pre-Inference Retrieval**: Queries dense semantic vector embeddings across the local vector database using Reciprocal Rank Fusion (RRF) to retrieve the top-\(K\) relevant historical memories and user preferences before formulating a prompt.
* **Post-Inference Mutation**: Automatically runs asynchronous background fact extraction to discover novel statements, detect contradictions, and issue deterministic `ADD`, `UPDATE`, or `DELETE` commands to maintain memory consistency across long horizons.

### 2. Dynamic Cost & Latency Model Routing
* Evaluates input complexity before allocating compute:
  * **Low-Complexity Tasks**: General queries, simple formatting, and high-frequency tool calls route to ultra-fast, low-cost models (**Gemini 3.8 Flash**).
  * **High-Complexity Tasks**: Architectural synthesis, multi-source reconciliation, and deep recursive reasoning escalate to high-reasoning models (**Claude 3.5 Sonnet / Gemini Thinking**).

### 3. Tree-of-Thoughts (ToT) & Graph RAG
* **Tree-of-Thoughts Engine**: Spawns multiple reasoning branches, evaluates intermediate states via heuristic evaluation functions, and backtracks upon encountering suboptimal trajectories.
* **Knowledge Graph RAG**: Maintains a structured entity-relation graph in SQLite alongside semantic vector indexes, allowing the agent to traverse relationships between people, projects, repositories, and historical decisions.

### 4. Enterprise Governance & Sovereign Killswitch
* **Budget Guardrails**: Enforces hard daily spend limits (USD) and token thresholds with proactive budget consumption warnings.
* **Sliding-Window Rate Limiting**: Protects execution endpoints from burst overload (120 req/min).
* **Emergency Killswitch**: Provides instant, system-wide process termination and lockfile generation via `scripts/kill.bat` or `scripts/killswitch.ps1`.

---

## 📂 Repository Layout

```text
ultron-memory-agent/
├── tests/                        # Automated unit & integration test suite
│   ├── __init__.py
│   ├── conftest.py               # Shared test fixtures & ROOT_DIR bootstrapping
│   ├── test_async_subprocess.py  # Asynchronous subprocess isolation test
│   ├── test_compaction.py        # Large tool output compaction verification
│   ├── test_isolation.py         # File ingestion isolation test
│   ├── test_model_routing.py     # Dynamic model triage test
│   ├── test_semantic_search.py   # Semantic vector search & RRF test
│   ├── test_tool_cache.py        # Tool output caching & bypass test
│   ├── test_tool_routing.py      # Dynamic tool routing & triage test
│   ├── verify_crewai_swarm.py    # CrewAI multi-agent swarm test
│   ├── verify_langchain_pipeline.py # LangChain tool-calling & memory test
│   ├── verify_langgraph_handoff.py  # LangGraph 2-step state machine test
│   └── verify_ledger_integration.py # Activity ledger & SSE verification
├── scripts/                      # Operational launchers & management utilities
│   ├── audit_all_systems.py      # Master 5-pillar architectural audit suite
│   ├── eval_benchmark.py         # Golden evaluation performance benchmark
│   ├── kill.bat                  # Emergency one-touch process killswitch (CMD)
│   ├── killswitch.ps1            # Emergency lockdown script (PowerShell)
│   ├── start_all.bat             # Concurrent launcher (Web HUD + Discord)
│   ├── start_discord.bat         # Standalone Discord bot bridge
│   └── start_web.bat             # Standalone FastAPI Web HUD
├── reference_data/               # Authoritative static datasets
│   ├── official_us_accounting_skills.json
│   └── sec_company_tickers.json
├── static/                       # Cybernetic Web HUD frontend assets (HTML/CSS/JS)
├── accounting_modules/           # US GAAP, bookkeeping, and payroll logic
├── tax_modules/                  # Corporate and individual tax modules
├── config.py                     # Centralized settings, dataclasses & env loader
├── agent.py                      # MemoryAgent core implementation
├── main.py                       # Rich terminal interactive CLI
├── app.py                        # FastAPI Cybernetic Web Mainframe
├── discord_bot.py                # Discord mobile & desktop bridge
├── pyproject.toml                # PEP 517/621 build config & tool settings
├── requirements.txt              # Production dependency specifications
├── LICENSE                       # MIT License
├── .env.example                  # Sanitized environment template
├── .gitignore                    # Zero-trust secret quarantine rules
└── README.md                     # System documentation
```

---

## 🚀 Quick Start

### 1. Prerequisites
* Python 3.10, 3.11, or 3.12
* Windows, Linux, or macOS

### 2. Environment Setup
```bash
# Clone the repository
git clone https://github.com/apparcora-app/ultron-memory-agent.git
cd ultron-memory-agent

# Create and activate virtual environment
python -m venv .venv

# Windows (Command Prompt / PowerShell)
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate

# Install production dependencies
pip install -r requirements.txt
```

### 3. Configuration
Copy the configuration template and populate your API credentials:
```bash
cp .env.example .env
```

Configure your preferred LLM provider in `.env`:
```ini
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key_here
VECTOR_STORE_PROVIDER=chroma
VECTOR_STORE_PATH=./data/chroma
```

### 4. Running the Agent

#### Interactive Rich CLI
```bash
python main.py
```
*CLI Slash Commands:*
* `/memories` — Inspect all memories stored in the vector store
* `/forget <id>` — Prune a specific memory entry
* `/clear` — Reset active session while retaining long-term memories
* `/quit` — Exit session

#### Cybernetic Web HUD (FastAPI)
```bash
# Direct launch
python app.py

# Or via operational launcher
scripts/start_web.bat
```
Navigate to `http://localhost:8000` to interact with the visual dashboard and live SSE event stream.

#### Discord Bot Gateway
```bash
python discord_bot.py
```

#### Launch All Services Concurrently
```cmd
scripts\start_all.bat
```

---

## 🧪 Testing & Verification

Run the test suite using pytest or run test scripts directly:

```bash
# Run tests with pytest
pytest tests/ -v

# Run targeted subsystem verifications
python tests/test_model_routing.py
python tests/test_compaction.py
python tests/test_tool_routing.py
python tests/verify_langchain_pipeline.py
python tests/verify_ledger_integration.py

# Run the master 5-pillar architectural audit
python scripts/audit_all_systems.py
```

---

## 🛡️ Zero-Trust Security & Secrets Isolation
* **Zero Hardcoded Secrets**: All credentials, tokens, and keys are strictly quarantined from version control and loaded dynamically at runtime via `.env`.
* **Local Vector Persistence**: All embeddings and memories default to local disk storage (`./data/chroma`), ensuring confidential memory records are never exfiltrated to external clouds.
* **Instant Emergency Lockdown**: Any system anomaly or runaway loop can be halted instantly using `scripts/kill.bat` or `scripts/killswitch.ps1`.

---

## 📄 License
This project is licensed under the terms of the [MIT License](LICENSE).
Author: **Hanzla Rehman** ([@apparcora-app](https://github.com/apparcora-app))
