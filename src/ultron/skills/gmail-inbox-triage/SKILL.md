---
name: gmail-inbox-triage
description: Triage a Gmail inbox into actionable buckets such as urgent, needs reply soon, waiting, and FYI using connected Gmail data. Use when the user asks to triage the inbox, rank what needs attention, find what still needs a reply, or separate important mail from noise.
category: AI & Agentic Systems
icon: 🤖
tags: [ai, agent, llm]
version: 1.1
updated_at: 2026-09-01
---
# gmail-inbox-triage

## Overview
Triage a Gmail inbox into actionable buckets such as urgent, needs reply soon, waiting, and FYI using connected Gmail data. Use when the user asks to triage the inbox, rank what needs attention, find what still needs a reply, or separate important mail from noise.

# Gmail Inbox Triage

## Overview

Use this skill for direct inbox-triage requests. Build on the core Gmail skill at [../gmail/SKILL.md](../gmail/SKILL.md), especially its search and thread-reading guidance.

## Workflow

1. Default to `INBOX` and a clear timeframe unless the user asks for a broader audit.
2. Use `search_emails` to build a shortlist before reading bodies.
3. Exclude obvious noise early if newsletters, calendar churn, or automated alerts dominate the first pass.
4. Use `batch_read_email` only when snippets are not enough to classify urgency or reply-needed status.
5. Escalate to `read_email_thread` when a message appears to be part of an active conversation and the surrounding thread may change the classification. Be careful because low-signal notifications can turn into long threads; `read_email_thread` exposes `total_messages`, which helps detect that.
6. Return the result in explicit Inbox Zero-style buckets such as `Urgent`, `Needs reply soon`, `Waiting`, and `FYI`.

## Bucket Heuristics

- `Urgent`: direct asks with time pressure, blocking messages, decision requests with deadlines, or operational mail that can break if ignored.
- `Needs reply soon`: direct asks without same-day urgency, active conversations where the user is the next responder, or follow-ups that will go stale if ignored.
- `Waiting`: threads where the user already replied or the current blocker belongs to someone else.
- `FYI`: announcements, newsletters, calendar churn, and transactional mail that does not require action.

## Output

- Include sender, subject, why each item is in its bucket, and the likely next action.
- State timeframe, search scope, and confidence.
- Treat reply-needed as an inference, not a guaranteed state.
- Avoid claiming the inbox is fully triaged if you only checked a narrow slice.

## 🧬 Evolution v1.1 — Binary encoding error in thread reader (2026-09-01)
* **Trigger Analysis**: The `read_email_thread` tool failed because it encountered an unknown binary encoding on message 5708, requiring a fallback to browser automation or snippet-based analysis.
- **Rule**: Catch API tool failures such as unknown binary encoding errors during `read_email_thread` or `read_email` executions.
- **Rule**: Immediately fallback to alternative inspection methods like `open_browser` to view messages in the web interface when raw API reading fails.
```
if tool_failed('read_email_thread'): open_browser(url='https://mail.google.com/mail/u/0/#search/from%3Adeloitte')
```
