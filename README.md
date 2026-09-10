# 🧠 Ultron Memory Agent

[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Vector Store](https://img.shields.io/badge/Vector%20Store-ChromaDB%20%7C%20Qdrant-green.svg)](https://www.trychroma.com/)
[![Memory Engine](https://img.shields.io/badge/Memory-Mem0-purple.svg)](https://github.com/mem0ai/mem0)
[![Orchestration](https://img.shields.io/badge/Orchestrator-LangGraph%20%7C%20CrewAI-orange.svg)](https://langchain-ai.github.io/langgraph/)

> **Ultron Memory Agent** is an enterprise-grade autonomous AI agentic architecture built on persistent long-term memory, dynamic multi-model reasoning triage, Tree-of-Thoughts (ToT) exploration, and multi-agent swarm orchestration.

---

## 🏛️ System Architecture

`	ext
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
│  │   • Tier 1 Fast / Daily (Gemini 3.8 Flash)                            │  │
│  │   • Tier 2 Deep Reasoning (Claude 3.5 Sonnet / DeepSeek-V3)           │  │
│  └──────────────────────────────────┬────────────────────────────────────┘  │
│                                     │                                       │
│  ┌──────────────────────────────────▼────────────────────────────────────┐  │
│  │                    Multi-Agent Orchestration Mesh                     │  │
│  │   • Hierarchical Planner & Goal DAG Manager                           │  │
│  │   • Tree-of-Thoughts (ToT) Multi-Branch Evaluation Engine             │  │
│  │   • Graph RAG & Episodic Trajectory Memory (ExpeL)                    │  │
│  │   • LangGraph State Machine & CrewAI Multi-Agent Swarms               │  │
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
│   • Execution Ledger Gate & Budget Guard (Hard Spend / Token Thresholds)   │
│   • In-Flight Critic Gate & Confidence Filter                               │
│   • Sovereign Emergency Killswitch (Cryptographically Signed Fast-Halt)     │
└─────────────────────────────────────────────────────────────────────────────┘
`

---

## ⚡ Key Highlights

### 1. Dual-Phase Memory Pipeline (Mem0 + Vector Store)
* **Retrieval Phase**: Queries vector embeddings using Reciprocal Rank Fusion (RRF) across ChromaDB and Qdrant to inject relevant historical context into the prompt before generating an answer.
* **Mutation Phase**: Runs fact extraction on conversation turns to detect updates and contradictions (e.g. correcting preferences) and dispatches clean ADD/UPDATE/DELETE operations.

### 2. Intelligent Cost & Complexity Router
* Incoming directives are triaged in real time:
  * **Low-complexity / Quick tool tasks** are routed to high-throughput, cost-effective models (**Gemini 3.8 Flash**).
  * **High-complexity / Architectural analysis** is escalated to deep-reasoning models (**Claude 3.5 Sonnet / DeepSeek-Chat**).

### 3. Tree-of-Thoughts (ToT) & Graph RAG
* Explores multiple solution trajectories concurrently using forward lookahead, heuristic scoring, and automatic backtracking for complex multi-step reasoning.
* Retains a persistent knowledge graph linking concepts, goals, and outcomes.

### 4. Enterprise Safety & Sovereign Killswitch
* **Budget Limits**: Configurable hard daily spending and token caps with early warning triggers.
* **Emergency Halt**: Instant cryptographic lockdown via scripts/kill.bat or scripts/killswitch.ps1 to stop all agent processes in emergency scenarios.

---

## 📂 Repository Structure

`	ext
ultron-memory-agent/
├── tests/                        # Comprehensive test & verification suite
│   ├── conftest.py               # Shared fixtures & path configuration
│   ├── test_model_routing.py     # Triage & LLM complexity test
│   ├── test_compaction.py        # Token & output compaction test
│   ├── test_tool_routing.py      # Dynamic tool dispatch verification
│   ├── verify_crewai_swarm.py    # CrewAI multi-agent integration test
│   └── verify_langgraph_handoff.py# LangGraph cyclic handoff test
├── scripts/                      # Operational & deployment launchers
│   ├── start_all.bat             # Launch Web HUD + Discord Gateway
│   ├── start_web.bat             # FastAPI Cybernetic Web HUD
│   ├── start_discord.bat         # Discord Bridge runner
│   ├── kill.bat                  # Emergency one-touch process killswitch
│   ├── killswitch.ps1            # PowerShell lockdown script
│   └── audit_all_systems.py      # Master 5-pillar architecture audit suite
├── reference_data/               # Authoritative datasets (SEC CIK tickers, etc.)
│   ├── sec_company_tickers.json
│   └── official_us_accounting_skills.json
├── static/                       # Web HUD frontend assets (HTML, CSS, JS)
├── accounting_modules/           # US GAAP, Bookkeeping, and Payroll engines
├── tax_modules/                  # Corporate and individual tax modules
├── config.py                     # Dataclasses, custom prompts & env loader
├── agent.py                      # MemoryAgent core implementation
├── main.py                       # Rich CLI interface & slash commands
├── app.py                        # FastAPI web mainframe
├── discord_bot.py                # Discord bot client
├── pyproject.toml                # Modern Python packaging & tool settings
├── requirements.txt              # Production dependency manifest
├── .env.example                  # Environment configuration template
├── .gitignore                    # Hardened security & privacy exclusions
└── README.md                     # Documentation
`

---

## 🚀 Quick Start

### 1. Prerequisites
* Python 3.10, 3.11, or 3.12
* (Optional) Docker Desktop if running Qdrant in a container (ChromaDB runs 100% locally with zero setup).

### 2. Installation
`ash
# Clone the repository
git clone https://github.com/apparcora-app/ultron-memory-agent.git
cd ultron-memory-agent

# Create and activate a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
`

### 3. Environment Configuration
Copy the template and configure your API keys:
`ash
cp .env.example .env
`
Edit .env to supply your credentials:
`ini
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
GEMINI_API_KEY=your_key_here
VECTOR_STORE_PROVIDER=chroma
`

### 4. Running the Agent

#### Interactive Rich CLI
`ash
python main.py
`
*CLI Slash Commands:*
* /memories — Inspect all long-term memories in the vector store
* /forget <id> — Prune a specific memory entry
* /clear — Reset active session history while retaining long-term memory
* /quit — Exit

#### Cybernetic Web HUD (FastAPI)
`ash
# Run standalone
python app.py
# Or use the launcher
scripts/start_web.bat
`
Navigate to http://localhost:8000 to interact with the visual dashboard.

#### Discord Bot Bridge
`ash
python discord_bot.py
`

#### Launch Everything Concurrently
`cmd
scripts\start_all.bat
`

---

## 🧪 Testing & Verification

Run the automated test suite using pytest:
`ash
# Run all unit tests
pytest tests/ -v

# Run specific integration verifications
python tests/test_model_routing.py
python tests/test_compaction.py
`

Run the master 5-pillar architecture audit:
`ash
python scripts/audit_all_systems.py
`

---

## 🛡️ Security & Privacy
* **Zero Hardcoded Secrets**: All sensitive keys and tokens are loaded strictly via .env (which is excluded from Git via .gitignore).
* **Air-Gapped Local Vector Storage**: When using ChromaDB, all embeddings and memories are persisted on the local filesystem (./data/chroma) without transmitting private memory records to third-party vector clouds.
* **Fail-Safe Killswitch**: Any anomaly can be halted immediately by running scripts/kill.bat.

---

## 📄 License
This project is licensed under the [MIT License](LICENSE).
