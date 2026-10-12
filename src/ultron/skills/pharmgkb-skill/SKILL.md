---
name: pharmgkb-skill
description: Submit compact PharmGKB API requests for genes, variants, clinical annotations, dosing guidelines, and search. Use when a user wants concise PharmGKB summaries
category: Frontend & Mobile UI
icon: ⚛️
tags: [frontend, ui, react, mobile]
version: 1.1
updated_at: 2026-09-01
---
# pharmgkb-skill

## Overview
Submit compact PharmGKB API requests for genes, variants, clinical annotations, dosing guidelines, and search. Use when a user wants concise PharmGKB summaries

## Operating rules
- Use `scripts/rest_request.py` for all PharmGKB API calls.
- Use `base_url=https://api.pharmgkb.org/v1/data`.
- Single object lookups usually do not need `max_items`; list and search endpoints are better with `max_items=10`.
- Re-run requests in long conversations instead of relying on older tool output.
- Treat displayed `...` in tool previews as UI truncation, not literal request content.

## Execution behavior
- Return concise markdown summaries from the script JSON by default.
- Prefer these paths: `gene/<id>`, `variant/<id>`, `clinicalAnnotation`, `dosingGuideline`, and search endpoints.
- If the user needs the full payload, set `save_raw=true` and report the saved file path.

## Input
- Read one JSON object from stdin.
- Required fields: `base_url`, `path`
- Optional fields: `method`, `params`, `headers`, `json_body`, `form_body`, `record_path`, `response_format`, `max_items`, `max_depth`, `timeout_sec`, `save_raw`, `raw_output_path`
- Common PharmGKB patterns:
  - `{"base_url":"https://api.pharmgkb.org/v1/data","path":"gene/PA36679"}`
  - `{"base_url":"https://api.pharmgkb.org/v1/data","path":"clinicalAnnotation","params":{"relatedChemicals.accessionId":"PA449726","limit":10},"max_items":10}`
  - `{"base_url":"https://api.pharmgkb.org/v1/data","path":"variant/PA166158545"}`

## Output
- Success returns `ok`, `source`, `path`, `method`, `status_code`, `warnings`, and either compact `records` or a compact `summary`.
- Use `raw_output_path` when `save_raw=true`.
- Failure returns `ok=false` with `error.code` and `error.message`.

## Execution
```bash
echo '{"base_url":"https://api.pharmgkb.org/v1/data","path":"gene/PA36679"}' | python scripts/rest_request.py
```

## References
- No additional runtime references are required; keep the import package limited to this file and `scripts/rest_request.py`.

## 🧬 Evolution v1.1 — Irrelevant SEC Tool Execution Context (2026-09-01)
* **Trigger Analysis**: The agent mistakenly executed SEC ticker python scripts while attempting to fulfill a PharmGKB bioinformatics request due to cross-task contamination.
- **Rule**: Strictly adhere to the domain-specific skill boundaries and never invoke financial or SEC scripts when executing a pharmgkb-skill runbook.
- **Rule**: Verify that the target API endpoint and helper script match the requested domain (PharmGKB REST requests via scripts/rest_request.py) before triggering any tool execution.
```
echo '{"base_url":"https://api.pharmgkb.org/v1/data","path":"gene/PA36679"}' | python scripts/rest_request.py
```
