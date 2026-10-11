# Security Policy

> **Status: personal use only. Not approved for client data. No approved LLM provider is configured.**

## Supported Versions

| Version | Supported |
|---|---|
| `main` branch | ✅ Active |
| Older commits | ❌ Not supported |

---

## Reporting a Vulnerability

**Do NOT open a public GitHub issue for security vulnerabilities.**

If you discover a security vulnerability in Ultron Memory Agent, please report it privately:

1. **Email:** `security@example.com` (or open a private GitHub Security Advisory)  
   Subject line: `[SECURITY] ultron-memory-agent — <brief description>`

2. Include in your report:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact assessment
   - Any suggested fixes (optional)

3. **Response SLA:**
   - Acknowledgement within **48 hours**
   - Status update within **7 days**
   - Fix or mitigation within **30 days** for critical issues

---

## Security Architecture

### Zero-Trust Secrets Model
- **Client Authentication**: All incoming requests require an X-API-Key header mapped to .env. Raw keys are immediately purged from memory and compared using cryptographic hashes (hmac.compare_digest).
- **Multi-Tenant Attribution**: Rate limits and spend budgets are strictly tracked per caller hash, preventing cross-tenant quota depletion.
- All API keys, tokens, and credentials are loaded exclusively from `.env` at runtime
- `.env` is quarantined from version control via `.gitignore`
- Never commit credentials — use `.env.example` as a sanitized template

### Local Memory Isolation
- All embeddings and memories default to local disk (`./data/chroma`)
- No confidential memory records are transmitted to external services unless explicitly configured with Qdrant Cloud

### Emergency Killswitch
- Any runaway process or anomaly can be halted instantly:
  ```bash
  # Windows CMD
  scripts\kill.bat

  # PowerShell
  scripts\killswitch.ps1
  ```
- This generates a `lockdown.flag` file that blocks all new agent operations

### Execution Governance
- Hard daily spend limits (USD) enforced by `governance/budget_tracker.py`
- Sliding-window rate limiter (120 req/min) prevents burst overload
- All tool executions are sandboxed via `infrastructure/sandbox.py`

### Dependency Vulnerability Scanning
Ultron Prime utilizes pip-audit to proactively scan for known Common Vulnerabilities and Exposures (CVEs) in all dependencies.

**Update Process:**
1. Run the automated audit script:
   `ash
   bash scripts/audit_deps.sh
   `
2. If vulnerabilities are found, the script will exit with a non-zero code and display the affected packages.
3. Update the package versions in 
equirements.txt to the recommended fix versions.
4. Regenerate the lockfile:
   `ash
   pip-compile --generate-hashes --output-file=requirements.lock requirements.txt
   `
5. Install the new dependencies and run the full test suite (pytest) to ensure no breaking changes were introduced.
6. Commit the updated 
equirements.txt and 
equirements.lock.

### Incident Response

If a security incident occurs (such as PII leakage or harmful agent actions), immediately refer to the [Incident Response Plan](docs/INCIDENT_RESPONSE.md) for step-by-step containment, investigation, and recovery procedures.


### Sandbox Limitations
As of 2026-10-05, the following limitations in \infrastructure/sandbox.py\ are acknowledged as accepted risks:
- **Imports & Code Execution:** While the AST validator blocks unauthorized imports (like \os\, \subprocess\, and \equests\), determined evasion techniques might bypass static analysis. Python executes with full user privileges.
- **File Access:** File paths were previously only restricted nominally, allowing access to standard drives (C:\). This gap has been narrowed, but deep permission restrictions rely on OS-level ACLs.
- **Resource Limits:** The sandbox relies on simple threading checks for memory limits (e.g., 512MB) and execution timeouts (e.g., 120s), which can be circumvented by native C extensions or aggressive allocation before the monitor thread polls.
- **Mitigation:** These risks are heavily mitigated by the Human-in-the-Loop (HITL) approval gate (\equire_approval\), which blocks unverified execution unless explicitly authorized by the operator.

## Accepted Architecture Risks

* **Backups on Same PC:** Backups are stored on the same PC (`D:` partition) for the current phase rather than true offsite/cloud storage.
* **Orphaned Process Cleanup:** Orphaned processes after a hard crash are not automatically cleaned up at runtime (`reaper.py` is a manual Notepad-only test utility located in `tests/manual/`).
* **Mem0 Purge Disabled for Personal Use:** `PURGE_MEM0=false` is maintained while storing only the operator's personal data (no clients onboarded).
* **#10 (Scalability ceiling untested beyond 6 agents):** The current swarm architecture operates with 6 specialized agents; pushing beyond this limit may risk deadlocks or context saturation.
* **#11 (Monitoring/alerting):** We rely on manual log inspection instead of proactive automated alerts.
* **#15 (Change approval):** There is no programmatic lock or review step enforcing changes to prompt and configuration files.
* **#17 (Deployment separation):** The environment lacks a strict boundary between development, staging, and production workspaces.
* **Unfixed dependencies:** chromadb, diskcache, and nltk contain known vulnerabilities but currently lack compatible fixes on PyPI. Mitigation: local-only, no network exposure, and re-check on each release.


### Client Data and LLM Providers
- **Provider Access**: Only approved providers (specifically Gemini Direct) are authorized to process confidential client data.
- **Free-Tier Limits**: Free-tier inference gateways (specifically FreeLLMAPI) must **only** be used for non-client tasks, sandbox evals, and internal non-sensitive workflows. No PII or client financials may ever be routed to these endpoints.

### Data Retention & PII Lifecycle Policy

Ultron Prime implements category-specific data retention windows and automated daily purge tasks (`pii_cleanup.py`).

| Category | Storage Path | Default Retention | Config Setting | Purpose / Policy |
|---|---|---|---|---|
| **Sessions** | `data/sessions/*.json` | 90 days | `SESSIONS_RETENTION_DAYS` | User & agent conversational turn state |
| **Telemetry DB** | `data/telemetry.db` (`audit_logs`) | 90 days | `TELEMETRY_RETENTION_DAYS` | Tool runtimes, token spend, call latency |
| **Computer Audit Log** | `data/logs/computer_audit.jsonl` | 365 days | `AUDIT_LOG_RETENTION_DAYS` | Complete audit trail for security compliance |
| **Blackboard** | `data/blackboard/*.json` | 30 days | `BLACKBOARD_RETENTION_DAYS` | Inter-agent working state & task memory |
| **Mem0 / Chroma Memory** | `data/chroma/` (`mem0_agent_claude`) | Retained (`PURGE_MEM0=false`) | `PURGE_MEM0` | Long-term memory facts & preferences |

> [!IMPORTANT]
> **Mem0 Personal Retention Exception**: While Ultron strictly holds the operator's personal data (no client data), `PURGE_MEM0` is kept `false` to preserve personal context and learned user preferences across sessions.
> **MANDATORY CLIENT ONBOARDING GATE**: Before any third-party or client data is ingested into Ultron, `PURGE_MEM0` MUST be set to `true` (with appropriate retention days) to ensure client PII is automatically purged under the retention SLA.
