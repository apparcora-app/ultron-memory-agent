---
name: Web Automation & Scraping Service
description: Automated web task execution service covering dynamic form filling, data extraction & web scraping, scheduled site monitoring, automated UI/API testing, and batch portal submissions using Playwright, Puppeteer, or Selenium.
category: Automation
icon: 🤖
tags: [web-automation, scraping, form-filling, testing, monitoring, cron, playwright, puppeteer, selenium, browser-use]
version: 1.1
updated_at: 2026-09-01
---
# 🤖 Web Automation & Scraping Protocol

Automated web task execution service covering form submission, structured web scraping, scheduled endpoint/page monitoring, and end-to-end browser automation.

---

## Core Capabilities for Ultron

1. **Automated Form Filling**:
   - Programmatically navigate to target URLs, fill input fields, select dropdowns, handle checkboxes, and submit forms.
2. **Web Scraping & Data Extraction**:
   - Extract structured tables, text, links, and media from dynamic JavaScript SPAs or static HTML pages.
3. **Scheduled Website & API Monitoring**:
   - Poll target URLs for price changes, inventory updates, status page downtime, or content shifts.
4. **Automated End-to-End Testing**:
   - Verify UI workflows, user authentication flows, checkout funnels, and API response status codes.
5. **Batch Submissions & Portal Sync**:
   - Automate multi-record data entry across web forms and administrative backends.

---

## Operational Execution Guidelines

When the user requests web automation or data scraping:

### 1. Form Filling Workflow
```python
# Playwright / Python execution pattern
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://example.com/form")
    page.fill('input[name="name"]', "Sample Client")
    page.fill('input[name="email"]', "client@example.com")
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")
    browser.close()
```

### 2. Structured Web Scraping
- Extract clean tabular datasets and save directly to `data/` or return formatted markdown tables.
- Handle pagination, infinite scroll, and dynamic content hydration.

### 3. Site Health & Status Monitoring
- Perform periodic health checks, measuring latency and verifying HTTP 200 OK responses.

---

## Standards & Error Handling
- **Auto-Retry**: Implement retry logic with exponential backoff on transient network failures.
- **Headless by Default**: Run automation headlessly unless the user explicitly requests visual browser inspection.
- **Clean Output**: Always report final submission confirmations, downloaded file paths, or extracted data tables cleanly to the user.

## 🧬 Evolution v1.1 — Desktop Application Control vs Browser Automation (2026-09-01)
* **Trigger Analysis**: The user requested interaction with local desktop applications instead of launching an isolated headless browser instance.
- **Rule**: Prioritize interacting with native desktop applications using OS-level automation tools (e.g., pywinauto, pyautogui, or direct application launching) when the user specifies desktop apps rather than web browsers.
- **Rule**: Clarify intent before spawning headless or automated web browsers if the user references local desktop software or UI elements outside the browser context.
```
import subprocess
# Launch local desktop app instead of web browser
subprocess.Popen(['start', 'notepad.exe'], shell=True)
```
