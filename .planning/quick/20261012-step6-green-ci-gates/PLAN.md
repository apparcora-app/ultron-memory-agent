# Quick Task: Step 6 Green CI Gates & Gitleaks

## Objective
Harden `.github/workflows/ci.yml` so that every check is genuine, non-advisory, and blocks pull requests on failures:
1. Integrate official **Gitleaks** secret detection action to guarantee zero leaked credentials, keys, or tokens.
2. Maintain strict **Ruff** lint gate on core packages (`core`, `memory`, `reasoning`, `security`, `governance`).
3. Add strict **Mypy** type checking on core hardened modules (`security/environment.py`, `core/profiles.py`, `memory/qdrant_store.py`, `memory/embeddings.py`) with zero `continue-on-error`.
4. Ensure test matrix and packaging checks run strictly and pass with 100% green status.
