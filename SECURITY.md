# Security Policy

## Supported Versions

| Version | Supported |
|---|---|
| `main` branch | ✅ Active |
| Older commits | ❌ Not supported |

---

## Reporting a Vulnerability

**Do NOT open a public GitHub issue for security vulnerabilities.**

If you discover a security vulnerability in Ultron Memory Agent, please report it privately:

1. **Email:** `reach.hanzla@gmail.com`  
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
