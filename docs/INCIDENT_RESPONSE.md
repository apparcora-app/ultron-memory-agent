# Incident Response Plan

This document outlines the procedures for handling security incidents in Ultron Prime. 

## Scenario A: Client PII Exposed or Leaked
*(e.g., SSN, EIN, or sensitive financial data found in unexpected logs, public repos, or third-party platforms)*

### 1. Detection
Identify the scope of the leak by checking the following audit trails:
- **Telemetry Database:** `data/telemetry.db`
- **Action Logs:** `data/logs/computer_audit.jsonl`
- **Memory/Sessions:** `data/sessions/`, `data/blackboard/`, and Chroma DB records.

### 2. Immediate Containment
Stop the bleeding immediately.
- **Engage Killswitch:** Instantly kill all agent processes and lock down the system.
  ```powershell
  powershell -File scripts\killswitch.ps1
  ```
- **Rotate Keys:** If API keys were compromised, immediately regenerate them in `.env`.
- **Revoke Tokens:** Go to the respective provider dashboards (OpenRouter, Google, Anthropic, Discord) and revoke the affected tokens.

### 3. Investigation
Determine exactly what was leaked and who is affected.
- Run queries against the telemetry database to find the compromised time window and records.
- Run a dry-run of the PII purge tool to see what records are flagged (can be configured for the specific timeframe):
  ```powershell
  python pii_cleanup.py --dry-run
  ```

### 4. Recovery
Remove the exposed data and restore from a safe state.
- **Purge Exposed Data:** Run the cleanup script to remove the PII from all local databases and files.
  ```powershell
  python pii_cleanup.py
  ```
- **Restore Safe Backup:** If the database is irrecoverably corrupted, restore from the last known good backup.
  ```powershell
  python scripts\restore.py <path_to_encrypted_backup_file>.enc
  ```

### 5. Notification Checklist
- [ ] **Employer / Organization Management:** Notify management immediately about the breach severity.
- [ ] **Affected Clients:** Draft a notification to affected clients detailing what data was exposed and mitigation steps taken.
- [ ] **IRS/FTC Duty:** For U.S. taxpayer data, consult the [IRS Data Theft Information for Tax Professionals](https://www.irs.gov/individuals/data-theft-information-for-tax-professionals) and FTC guidelines. (Report to local IRS Stakeholder Liaison).

---

## Scenario B: Agent Took a Wrong or Harmful Action
*(e.g., deleted critical files, sent an unauthorized email, misconfigured a client environment)*

### 1. Detection
Find out exactly what the agent did.
- **Review Computer Audit:** Check the raw action logs to see the exact tool calls and commands executed.
  ```powershell
  Get-Content data\logs\computer_audit.jsonl -Tail 50
  ```
- **Review Interaction Logs:** Check `data\interaction_log.jsonl` for the LLM reasoning that led to the action.

### 2. Immediate Containment
Halt the agent before it can do more damage.
- **Engage Killswitch:**
  ```powershell
  powershell -File scripts\killswitch.ps1
  ```
- **Disable Tool Execution:** Temporarily disable the agent's ability to act by setting `TOOL_EXECUTION_ENABLED=false` in `.env`.

### 3. Investigation
Identify the blast radius.
- Which systems were touched? (e.g., local files, emails sent, API calls made).
- Determine if the action was caused by a hallucination, a malicious prompt injection, or a logic bug in a tool.

### 4. Recovery
Revert the harmful action.
- **File System:** If local files were deleted or corrupted, restore them from the latest backup.
  ```powershell
  python scripts\restore.py <path_to_backup_archive>.enc
  ```
- **External Systems:** Manually log into affected third-party services (e.g., email provider, CRM) and revert the agent's actions (e.g., send correction emails, undo API writes).

### 5. Notification Checklist
- [ ] **Affected Clients/Users:** If the action affected an external user, notify them of the error and the correction.
- [ ] **Employer / Organization Management:** Report the incident if business operations were disrupted.

---

## Post-Incident Review Template
After the incident is resolved, document the following in a new report under `docs/incidents/`:

- **Incident Summary:** What happened, when, and who discovered it?
- **Root Cause:** Why did this happen? (e.g., prompt injection, missing guardrail, dependency vulnerability).
- **Timeline:** Chronological list of events from detection to resolution.
- **Action Items:** 
  - What code changes are needed to prevent this?
  - What new tests must be written?
  - Are there new telemetry events we need to track?
