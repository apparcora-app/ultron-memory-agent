# Contributing to Ultron Memory Agent

Thank you for your interest in contributing! Ultron is an enterprise-grade autonomous AI cognitive system — contributions are held to a high standard.

## Code of Conduct
Please be respectful and constructive. Harassment of any kind will not be tolerated.

---

## Getting Started

### 1. Fork & Clone
```bash
git clone https://github.com/<your-username>/ultron-memory-agent.git
cd ultron-memory-agent
```

### 2. Set Up Development Environment
```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
pip install ruff mypy pytest pytest-asyncio pytest-cov
```

### 3. Configure
```bash
cp .env.example .env
# Fill in your API keys
```

### 4. Verify Setup
```bash
make lint    # or: ruff check .
make test    # or: pytest tests/ -v
```

---

## Branch Naming Convention

| Prefix | Use case |
|---|---|
| `feat/` | New features or capabilities |
| `fix/` | Bug fixes |
| `refactor/` | Code restructuring without behavior change |
| `docs/` | Documentation only |
| `chore/` | CI, tooling, dependency updates |
| `test/` | Adding or improving tests |

Examples: `feat/qdrant-hybrid-search`, `fix/memory-deduplication-race`, `docs/api-reference`

---

## Commit Convention

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short summary>

[optional body]

[optional footer: Closes #N]
```

**Types:** `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `ci`

**Scopes:** `memory`, `reasoning`, `pipelines`, `governance`, `guardrails`, `infra`, `ci`

Examples:
```
feat(memory): add Qdrant hybrid dense-sparse retrieval
fix(governance): prevent budget overflow on concurrent requests  
chore(ci): pin ruff to 0.4.x for reproducible linting
```

---

## Code Style

All Python code is linted with **[ruff](https://docs.astral.sh/ruff/)**:

```bash
ruff check .          # lint
ruff check . --fix    # auto-fix safe issues
ruff format .         # format (Black-compatible)
```

The configuration lives in `pyproject.toml` under `[tool.ruff]`. Please do not disable rules per-file without a documented reason.

---

## Testing

- All new features **must** include unit tests in `tests/`.
- Test files follow the `test_<module>.py` naming convention.
- Fixtures and sample data live in `tests/fixtures/`.
- Run the full suite: `pytest tests/ -v --tb=short`

---

## Pull Request Process

1. Ensure `ruff check .` and `pytest tests/ -v` pass locally.
2. Add a one-line entry to `CHANGELOG.md` under `[Unreleased]`.
3. Fill in the PR template completely.
4. Request a review from `@apparcora-app`.
5. Once approved and CI is green, the maintainer will squash-merge.

---

## Architecture Overview

Before contributing, familiarise yourself with the package layout:

| Package | Responsibility |
|---|---|
| `core/` | Agent runtime, model router, tool definitions |
| `memory/` | Dual-phase memory pipeline, vector persistence |
| `reasoning/` | ToT engine, Graph RAG, hierarchical planner |
| `pipelines/` | LangGraph, CrewAI, multi-agent mesh |
| `interfaces/` | CLI (`main.py`), FastAPI (`app.py`), Discord bot |
| `infrastructure/` | MCP client, sandbox, file processor, email |
| `governance/` | Budget tracker, execution ledger |
| `guardrails/` | Critic gate, anti-fabrication, artifact verification |
| `security/` | Killswitch, lockdown, secrets |
| `telemetry/` | Metrics, tracing, event bus |
| `accounting_modules/` | GAAP, bookkeeping, payroll |
| `tax_modules/` | Corporate & individual tax workflows |
