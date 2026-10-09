# Manual Diagnostic & Verification Tests (`tests/manual/`)

This directory contains standalone manual verification, stress, failover, and diagnostic scripts. These scripts are intentionally excluded from automated pytest CI/CD runs.

---

## 🚀 How to Run

Always execute these scripts from the repository root:
```bash
python tests/manual/<script_name>.py
```
Each script is equipped with an automated root header:
```python
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
```
This ensures `sys.path[0]` and the current working directory resolve directly to the repository root, allowing root-level module imports (`agent`, `app`, `core`, `telemetry`, etc.) and relative file accesses (`data/`, `logs/`, etc.) to work seamlessly.

---

## ⚠️ High-Risk Scripts (DO NOT RUN CASUALLY)

The following 7 scripts perform disruptive OS-level operations (spawning/killing Notepad processes, calling `os._exit()`, or modifying state files) and **MUST NOT** be run casually or in automated environments:

| Script | High-Risk Behavior / Rationale | Safe Verification Mode |
|---|---|---|
| `reaper.py` | Kills active `notepad.exe` processes by PID pattern | `python -m py_compile` & import check only |
| `test_runner.py` | Spawns multiple `notepad.exe` instances and checks process table | `python -m py_compile` & import check only |
| `test_orphans.py` | Spawns 10 background `notepad.exe` instances via ToolExecutor | `python -m py_compile` & import check only |
| `test_orphans_sigkill.py` | Spawns Notepad and terminates abruptly via `os._exit()` | `python -m py_compile` & import check only |
| `test_focus.py` | Spawns `notepad.exe` and `calc.exe` to test GUI focus stealing | `python -m py_compile` & import check only |
| `test_access_denied.py` | Spawns Notepad to test permission / sandbox restrictions | `python -m py_compile` & import check only |
| `test_21_point.py` | Overwrites `audit_21_report.md` and runs multiple subprocess tests | `python -m py_compile` & import check only |

---

## 📋 Inventory of Manual Test Scripts (34 Total)

1. `reaper.py` — Orphan process reaper test
2. `test_runner.py` — Notepad process leak test runner
3. `test_21_point.py` — 21-point architecture and governance verification
4. `test_failover6.py` — Tiered provider failover stress test
5. `test_failover_trace.py` — Trace propagation across failover events
6. `test_perfect_clean.py` — Clean agent execution verification
7. `test_clean_run.py` — Standard agent runtime validation
8. `test_normal_run_python.py` — Standard python execution driver test
9. `test_adversarial_402.py` — Rate-limit / 402 payment required adversary test
10. `test_adversarial_swallow.py` — Error swallow resistance check
11. `test_adversarial_langgraph_fresh.py` — LangGraph adversarial failure injection
12. `test_adversarial_interceptor3.py` — Tool interceptor bypass adversary test
13. `test_concurrent_chroma_auth.py` — ChromaDB multi-tenant concurrent auth test
14. `test_concurrent_chroma_async.py` — ChromaDB asynchronous concurrent read/write
15. `test_ledger.py` — Execution ledger verification
16. `test_ledger_gate.py` — Ledger approval gate verification
17. `test_mem_infer.py` — Mem0 inference parameter isolation test
18. `test_mem_quota_fail_isolated.py` — Mem0 quota failure handling test
19. `test_mem_direct.py` — Direct memory manager lookup test
20. `test_orphans.py` — Subprocess orphan tracking test
21. `test_orphans_sigkill.py` — Hard crash (SIGKILL/os._exit) orphan test
22. `test_pii_sinks.py` — PII redaction sinks validation
23. `test_pii_terminal.py` — Live terminal PII output verification
24. `test_api_auth.py` — External API key validation & per-caller rate limit
25. `test_access_denied.py` — Sandbox permission denial verification
26. `test_dream_auth.py` — Dreaming engine authentication check
27. `test_approval.py` — Human-in-the-loop approval gate test
28. `test_hitl.py` — Interactive HITL prompt test
29. `test_sandbox_gaps.py` — Security sandbox boundary & gap test
30. `test_burst.py` — Rapid request burst / concurrency stress test
31. `test_client_data.py` — Client confidential data routing barrier test
32. `test_freellm.py` — FreeLLMAPI direct connection verification
33. `test_focus.py` — Windows desktop window focus management test
34. `test_prompt_management.py` — Dynamic system prompt configuration test
