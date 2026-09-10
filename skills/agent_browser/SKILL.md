---
name: Agent Browser Automation CLI
description: Headless browser automation CLI optimized for AI agents with accessibility tree snapshots and ref-based deterministic element selection (@e1, @e2).
category: Automation
icon: 🌐
tags: [browser, automation, playwright, web-scraping, headless, cli, agent-browser, testing]
version: 1.3
updated_at: 2026-09-02
---
# 🌐 Agent Browser Automation Skill

Fast, deterministic headless browser automation using accessibility tree snapshots with interactive element refs (`@e1`, `@e2`, `@e3`).

## Core Execution Workflow for Ultron

```bash
# 1. Navigate and capture interactive snapshot
agent-browser open https://example.com
agent-browser snapshot -i --json

# 2. Parse element refs from JSON, then interact
agent-browser click @e2
agent-browser fill @e3 "text"

# 3. Re-snapshot after DOM mutation
agent-browser snapshot -i --json
```

## Key Command Protocols

### 1. Navigation & State
- `agent-browser open <url>`
- `agent-browser back | forward | reload | close`
- `agent-browser wait --load networkidle`
- `agent-browser wait @e2`

### 2. Snapshots (Always use `-i --json`)
- `agent-browser snapshot -i --json` — Interactive elements in JSON format
- `agent-browser snapshot -i -c -d 5 --json` — Compact tree with depth limit 5
- `agent-browser snapshot -s "#main" -i` — Scope to specific CSS selector

### 3. Interactions (Ref-Based)
- `agent-browser click @e2`
- `agent-browser fill @e3 "input text"`
- `agent-browser type @e3 "input text"`
- `agent-browser select @e6 "value"`
- `agent-browser press "Enter"`
- `agent-browser scroll down 500`

### 4. Data Extraction
- `agent-browser get text @e1 --json`
- `agent-browser get html @e2 --json`
- `agent-browser get value @e3 --json`
- `agent-browser get attr @e4 "href" --json`
- `agent-browser get title --json`
- `agent-browser get url --json`

### 5. Session Isolation & Auth Storage
- `agent-browser --session admin open app.com`
- `agent-browser state save auth.json` — Save cookies/session storage
- `agent-browser state load auth.json` — Load auth state (skip repeated logins)

### 6. Visual Media
- `agent-browser screenshot page.png`
- `agent-browser pdf page.pdf`

## Best Practices
1. Always use `-i --json` to get clean JSON refs for buttons, links, and inputs.
2. Wait for page load: `agent-browser wait --load networkidle`.
3. Save state to bypass repeated logins on SaaS portals.

## 🧬 Evolution v1.1 — Desktop Application vs Web Browser Confusion (2026-09-01)
* **Trigger Analysis**: The agent attempted to use the headless browser automation CLI for a native desktop application that was already installed and logged in locally.
- **Rule**: Verify whether the target application is a native desktop app or a web application before invoking the agent-browser skill.
- **Rule**: If the target is a local desktop application already running or accessible via local shell commands, bypass the browser CLI entirely and interact with the OS or open the app directly.
```
start /path/to/desktop/app  # or use OS-level execution for native desktop applications
```

## 🧬 Evolution v1.2 — Direct URL Construction vs Search Navigation (2026-09-02)
* **Trigger Analysis**: The agent directly opened a pre-formulated Google search URL instead of utilizing the browser CLI's dedicated navigation and search interaction workflow for user-intent queries.
- **Rule**: When a user requests information retrieval like a weather forecast, prefer opening the target search engine or weather provider homepage directly, or use the interactive search input field rather than hardcoding search query parameters into the open command unless explicitly requested.
- **Rule**: Always follow up browser initialization with a snapshot (`agent-browser snapshot -i --json`) to inspect interactive elements before performing actions.
```
agent-browser open https://www.google.com
agent-browser snapshot -i --json
agent-browser fill @e1 "New York weather forecast today"
agent-browser press "Enter"
```

## 🧬 Evolution v1.3 — Direct URL Construction vs Search Query (2026-09-02)
* **Trigger Analysis**: The agent navigated directly to a Google search URL instead of utilizing the CLI's native navigation and search flow properly or leveraging direct weather URLs.
- **Rule**: When a user asks for weather or dynamic localized info, navigate directly to a reliable provider (e.g., wttr.in or weather.com) or use the search engine cleanly via `agent-browser open`.
- **Rule**: Ensure browser commands explicitly handle search queries by encoding URLs properly or interacting with the search input field if starting from a homepage.
```
agent-browser open "https://wttr.in/New+York?format=3"
```
