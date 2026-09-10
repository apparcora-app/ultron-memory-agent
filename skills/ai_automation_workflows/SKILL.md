---
name: AI Automation & Multi-Model Pipelines
description: Build automated AI workflows combining multiple models, APIs, and cloud services. Orchestrates batch processing, sequential pipelines, parallel asset generation, conditional routing, retry fallbacks, and scheduled cron jobs via CLI and Python.
category: Automation
icon: ⚡
tags: [ai-automation, workflow, batch-processing, pipelines, orchestration, cron, multi-model, infsh, automation-script, python-sdk]
---

# ⚡ AI Automation & Multi-Model Pipelines

Build automated, resilient AI workflows combining multiple frontier models, image generators, search agents, and data processing scripts.

---

## Core Orchestration Patterns for Ultron

### 1. Sequential Content Pipeline
Chain specialized models across distinct stages: Research ➔ Synthesis ➔ Visual Asset Generation ➔ Multi-Platform Distribution.

```bash
# Step 1: Research
RESEARCH=$(infsh app run tavily/search-assistant --input '{"query": "Latest GAAP accounting updates"}')

# Step 2: Synthesis (Claude Sonnet 5)
ARTICLE=$(infsh app run openrouter/claude-sonnet-45 --input "{\"prompt\": \"Draft an executive briefing based on: $RESEARCH\"}")

# Step 3: Visual Generation (Flux / Imagen)
IMAGE=$(infsh app run falai/flux-dev --input '{"prompt": "Executive modern financial chart hero graphic"}')
```

### 2. High-Throughput Batch Processing
Process large arrays of inputs with rate-limiting and structured JSON output storage:

```python
import time
import json
from pathlib import Path

prompts = ["Market Analysis", "Risk Assessment", "Valuation Multiples"]
output_dir = Path("data/processed_reports")
output_dir.mkdir(parents=True, exist_ok=True)

for p in prompts:
    # Run model processing with rate limiting
    time.sleep(1.5)
```

### 3. Parallel Asset Generation
Run concurrent async jobs for independent deliverables (Hero graphics, thumbnail variants, social copy):

```bash
infsh app run falai/flux-dev --input '{"prompt": "Graphic 1"}' > g1.json &
PID1=$!
infsh app run falai/flux-dev --input '{"prompt": "Graphic 2"}' > g2.json &
PID2=$!
wait $PID1 $PID2
```

### 4. Conditional Content Routing & Fallbacks
- Classify sentiment or intent using lightweight models (e.g. Haiku 4.5) before routing to heavy reasoning models (Sonnet 5).
- Implement exponential backoff retry loops with secondary fallback models if primary endpoints time out.

### 5. Scheduled Automation (Cron / Heartbeat)
- Deploy periodic cron scripts for morning briefings, portfolio metric scans, or automated daily content calendars.

---

## Engineering Best Practices
1. **Idempotency**: Always ensure scripts can be safely re-run without duplicating records.
2. **Intermediate Checkpoints**: Save raw outputs as JSON before subsequent transform steps.
3. **Graceful Degradation**: Always provide fallback handlers for third-party API rate limits.
