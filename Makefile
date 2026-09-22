.PHONY: install dev lint format typecheck test audit run-cli run-web run-discord docker-up docker-down clean help

# ── Variables ──────────────────────────────────────────────────────────────────
PYTHON      := python
PIP         := pip
PYTEST      := pytest
RUFF        := ruff
MYPY        := mypy
VENV        := .venv
TESTS       := tests/

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Setup ──────────────────────────────────────────────────────────────────────
install: ## Install production dependencies
	$(PIP) install -r requirements.txt

dev: ## Install production + development dependencies
	$(PIP) install -r requirements.txt
	$(PIP) install ruff mypy pytest pytest-asyncio pytest-cov

# ── Code Quality ───────────────────────────────────────────────────────────────
lint: ## Run ruff linter
	$(RUFF) check .

format: ## Auto-format with ruff (Black-compatible)
	$(RUFF) format .
	$(RUFF) check . --fix

typecheck: ## Run mypy type checker (advisory)
	$(MYPY) . --ignore-missing-imports --no-error-summary

# ── Testing ────────────────────────────────────────────────────────────────────
test: ## Run the full test suite
	$(PYTEST) $(TESTS) -v --tb=short --ignore=$(TESTS)fixtures

test-cov: ## Run tests with coverage report
	$(PYTEST) $(TESTS) -v --cov=. --cov-report=term-missing --ignore=$(TESTS)fixtures

audit: ## Run the master 5-pillar architectural audit
	$(PYTHON) scripts/audit_all_systems.py

# ── Running Interfaces ─────────────────────────────────────────────────────────
run-cli: ## Start the Rich terminal CLI
	$(PYTHON) main.py

run-web: ## Start the FastAPI Cybernetic Web HUD (localhost:8000)
	$(PYTHON) app.py

run-discord: ## Start the Discord bot gateway
	$(PYTHON) discord_bot.py

# ── Docker ─────────────────────────────────────────────────────────────────────
docker-up: ## Build and start all services with Docker Compose
	docker-compose up --build -d

docker-down: ## Stop all Docker services
	docker-compose down

docker-logs: ## Tail logs for all Docker services
	docker-compose logs -f

# ── Cleanup ────────────────────────────────────────────────────────────────────
clean: ## Remove Python bytecode, caches, and build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	find . -name "*.pyc" -delete 2>/dev/null; true
	rm -rf .pytest_cache .ruff_cache .mypy_cache build dist *.egg-info
