### Point 1: Core pillars: perception/input, reasoning/planning, tool use, orchestration (6-agent swarm), feedback/evaluation (Vanguard critic), learning/adaptation, short and long-term memory
**Status:** PRESENT (proven)
<details><summary>Raw Proof</summary>

```text
class MemoryAgent:
# Relocated to: pipelines/crewai_pipeline.py
#   from crewai_pipeline import X   -> re-exported below
#   python crewai_pipeline.py                                                              -> forwarded below
    from pipelines.crewai_pipeline import *       # noqa: F401 F403 E402
        from pipelines.crewai_pipeline import __all__  # noqa: F401 E402
    _rp = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), r"pipelines/crewai_pipeline.py")
```
</details>

### Point 2: Verification layer integrity: handoff under a fresh induced failure, spot-check 3 'accepted risk' exception blocks in agent.py, killswitch.py and failover.py intact
**Status:** PARTIAL
<details><summary>Raw Proof</summary>

```text
"Ensure impeccable precision, highlight discrepancy risks, and structure financial data clearly for Boss."
killswitch.ps1
Missing pieces

File Not Found
```
</details>

### Point 3: Security/safety: permissioning, secrets management, rate limiting, injection resistance/sandbox, human-in-the-loop approval gate
**Status:** PRESENT (proven)
<details><summary>Raw Proof</summary>

```text
--- Test File Escape ---
PASSED: Blocked file access
--- Test import os ---
PASSED: Blocked import os
--- Test import subprocess ---
PASSED: Blocked import subprocess
--- Test network call ---
PASSED: Blocked network call
--- Test run forever ---
PASSED: Blocked infinite loop with timeout
--- Test memory cap ---
PASSED: Blocked memory exhaustion
```
</details>

### Point 4: Durability: os._exit + reaper test, restart recovery, retry/failover, resource leaks
**Status:** PRESENT (proven)
<details><summary>Raw Proof</summary>

```text
os._exit(1)
                os._exit(1)
```
</details>

### Point 5: Deployment and versioning: CI/CD, prompt/config version control, rollback plan
**Status:** PRESENT (proven)
<details><summary>Raw Proof</summary>

```text
ci.yml
```
</details>

### Point 6: Testing: regression suite exists and is independent of telemetry
**Status:** PARTIAL
<details><summary>Raw Proof</summary>

```text
Command 'pytest tests/test_sandbox_gaps.py -v' timed out after 10 seconds
```
</details>

### Point 7: Data governance: PII flow to LLM providers, client data in logs, retention policy
**Status:** PRESENT (proven)
<details><summary>Raw Proof</summary>

```text
test_pii_purge.ps1
```
</details>

### Point 8: Model routing/provider fallback: route_reason and model_display fire correctly
**Status:** PARTIAL
<details><summary>Raw Proof</summary>

```text
Missing router
```
</details>

### Point 9: Documentation: architecture doc, onboarding without tribal knowledge
**Status:** PRESENT (proven)
<details><summary>Raw Proof</summary>

```text
README.md
INCIDENT_RESPONSE.md
```
</details>

### Point 10: Scalability ceiling: swarm behavior beyond 6 agents
**Status:** PARTIAL
<details><summary>Raw Proof</summary>

```text
Not verified beyond 6
```
</details>

### Point 11: Monitoring/alerting: proactive notifications vs manual log checks
**Status:** MISSING
<details><summary>Raw Proof</summary>

```text
No proactive alerts

FINDSTR: Cannot open governance\telemetry.py
```
</details>

### Point 12: Concurrency: concurrent ChromaDB read/write from two agents
**Status:** MISSING
<details><summary>Raw Proof</summary>

```text
No concurrency test found
```
</details>

### Point 13: Backup and disaster recovery: off-machine backup and a tested restore
**Status:** PRESENT (proven)
<details><summary>Raw Proof</summary>

```text
backup.py
restore.py
```
</details>

### Point 14: Explainability: can a past decision be reconstructed from logs
**Status:** PRESENT (proven)
<details><summary>Raw Proof</summary>

```text
computer_audit.jsonl
```
</details>

### Point 15: Change approval: review step before prompt/config changes
**Status:** PARTIAL
<details><summary>Raw Proof</summary>

```text
audit_21_report.md:### Point 15: Change approval: review step before prompt/config changes
audit_21_report.md:CONTRIBUTING.md:4. Request a review from `@apparcora-app`.
audit_21_report.md:README.md:├── CODEOWNERS                    # Auto-assign PR reviewers
audit_21_report.md:STITCH_WORKFLOW.md:### Step C: Local Preview & Hot Reloading
audit_21_report.md:STITCH_WORKFLOW.md:Preview at `http://localhost:5173`.
CONTRIBUTING.md:4. Request a review from `@apparcora-app`.
README.md:├── CODEOWNERS                    # Auto-assign PR reviewers
STITCH_WORKFLOW.md:### Step C: Local Preview & Hot Reloading
STITCH_WORKFLOW.md:Preview at `http://localhost:5173`.
```
</details>

### Point 16: External API: authentication, per-caller rate limiting, input validation
**Status:** PRESENT (proven)
<details><summary>Raw Proof</summary>

```text
api_key = request.headers.get("X-API-Key")
        return JSONResponse(status_code=401, content={"detail": "Missing X-API-Key header"})
```
</details>

### Point 17: Environment separation: dev/staging/prod
**Status:** MISSING
<details><summary>Raw Proof</summary>

```text
No env separation
```
</details>

### Point 18: Dependency security: pinned versions, vulnerability scanning
**Status:** PRESENT (proven)
<details><summary>Raw Proof</summary>

```text
requirements.lock
audit_deps.sh
```
</details>

### Point 19: Cost tracking: spend attribution per task/client
**Status:** PRESENT (proven)
<details><summary>Raw Proof</summary>

```text
budget_tracker.py
```
</details>

### Point 20: Incident response plan: exists in docs and its commands work
**Status:** PRESENT (proven)
<details><summary>Raw Proof</summary>

```text
INCIDENT_RESPONSE.md
```
</details>

### Point 21: Legal/liability boundary: sign-off required for irreversible actions
**Status:** PARTIAL
<details><summary>Raw Proof</summary>

```text
No explicit sign-off found
```
</details>
