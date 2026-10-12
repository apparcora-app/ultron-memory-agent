---
name: Cold Outreach & Intent-Based Conversion Framework
description: High-converting cold outreach engine for B2B, local businesses, LinkedIn DMs, SMS, and Upwork proposals based on Hormozi's $100M Leads, PAS, BAB, and AIDA copywriting frameworks.
category: Sales
icon: 🎯
tags: [cold-email, outreach, sales, b2b, hormozi, copywriting, proposals, linkedin, upwork, conversion, follow-up, lead-generation]
version: 1.4
updated_at: 2026-09-02
---
# 🎯 Cold Outreach — Intent-Based Conversion Framework

Generate high-converting cold emails, SMS, LinkedIn DMs, and Upwork proposals using battle-tested frameworks from Alex Hormozi's *$100M Leads*, Cleverly, and multi-touch sequence engineering.

---

## 1. Instant-Delete Traps (Never Do These)
- ❌ **Ego-Centric Openers**: *"We are the leading..."*, *"I'm excited to share..."* (Prospects do not care about you yet).
- ❌ **"Hope this finds you well" / "Circling back" / "Bumping this"**: Signals zero value and automated spam.
- ❌ **Hard Sell in Email #1**: Asking for a 30-minute call or demo before demonstrating undeniable value.
- ❌ **Wall of Text**: Keep initial cold emails strictly between **50–100 words**.

---

## 2. Hormozi's 4-Step Cold Outreach Engine

1. **Build the List (ICP-First)**: Target specific triggers (new hires, bad reviews, lack of booking automation, recent funding).
2. **Personalize with External Evidence**: Reference specific website pages, tech stack gaps, or visible friction points.
3. **Lead with Free Value (Lead Magnet)**: Provide a free audit, a plug-and-play playbook, or a 2-minute Loom walkthrough.
4. **Multi-Touch Sequence (3–5 Touches)**: Deliver new value on every touchpoint spaced 3–5 days apart.

---

## 3. Copywriting Frameworks for Ultron

### PAS (Problem, Agitate, Solve)
> **[Problem]**: Noticed [Company] doesn't have [specific automation/feature].  
> **[Agitate]**: Most [business type] in [area] lose $[X] monthly because of this.  
> **[Solve]**: We helped [similar client] solve this in [timeframe] resulting in [specific metric].  
> **[Soft Ask]**: Worth 5 minutes to see the breakdown?

### BAB (Before, After, Bridge)
> **[Before]**: Right now, [Company] handles [pain point] manually.  
> **[After]**: Imagine [desired outcome — e.g. 100% automated client reconciliation without manual entry].  
> **[Bridge]**: We built a lightweight workflow for [competitor/peer] that achieved this in 14 days.  
> **[Soft Ask]**: Want me to send the 2-minute overview?

### The Executive One-Liner (SMS / Short Follow-Up)
> *"Saw [Company] is still using [old tool] — helped [peer client] cut [pain point] by [X%]. Worth a quick look?"*

---

## 4. Multi-Channel Touch Sequence

| Touch | Day | Channel | Framework | Objective |
| :---: | :---: | :---: | :--- | :--- |
| **1** | Day 0 | Email | PAS / BAB (50–90 words) | Problem-aware hook + free value offer |
| **2** | Day 3 | LinkedIn | Connection (<300 chars) | Profile touch + engage recent post |
| **3** | Day 5 | Email | Value-Add Case Study | Share tactical breakdown/ROI metric |
| **4** | Day 9 | Email / SMS | One-Liner Observation | Low-friction question |
| **5** | Day 14 | Email | Breakup / Closing Loop | Graceful close, zero desperation |

---

## 5. Freelance & Upwork Proposal Framework
1. **Direct Proof of Reading**: Reference the client's exact problem in the first sentence.
2. **Quantified Credibility**: *"Built [similar solution] ➔ generated [outcome] in [timeframe]."*
3. **De-Risk the First Step**: *"Happy to deliver [small initial milestone] first so you can review before committing."*
4. **Clear Actionable CTA**: *"Are you free for a 5-minute chat today or should I drop the loom link here?"*

## 🧬 Evolution v1.1 — GUI Window Focus Race Condition (2026-09-02)
* **Trigger Analysis**: The GUI automation tools aborted keystrokes because the agent mainframe browser window intercepted active focus before the target application stabilized.
- **Rule**: Always introduce a brief pause or verification loop to ensure the target GUI window has fully gained and held active focus before dispatching keystrokes.
- **Rule**: Explicitly re-foreground the target application window if a mismatch error is detected during execution.
```
control_desktop_gui(action='bring_to_foreground', window_title='Untitled - Notepad'); sleep(1.0); control_desktop_gui(action='send_keys', keys='Greeting')
```

## 🧬 Evolution v1.2 — Generic Broadcast vs Targeted Outreach (2026-09-02)
* **Trigger Analysis**: The system processed a generic social media greeting ('Hello LinkedIn Network') by simply saving it to Notepad, failing to apply the cold outreach copywriting frameworks or personalization rules.
- **Rule**: Never treat generic social media broadcast greetings as valid outreach targets; always convert them into structured, high-value B2B sequences targeting a specific ICP.
- **Rule**: Do not execute system tool actions like writing to Notepad for draft storage unless explicitly instructed; output the generated copy directly to the communication interface.
```
if 'linkedin network' in directive.lower(): apply_pas_framework(target_icp='LinkedIn Prospects')
```

## 🧬 Evolution v1.3 — Robotic Self-Introduction Jargon Trap (2026-09-02)
* **Trigger Analysis**: The agent fell into the ego-centric trap by outputting a highly technical, jargon-heavy architectural self-description rather than a brief, conversational, and engaging introduction.
- **Rule**: When introducing the Ultron persona, strictly avoid technical system jargon (such as 'persistent vector memory', 'multi-agent mainframe', 'protocol layers') and keep the self-description ultra-simple, conversational, and human-friendly.
- **Rule**: Ensure any self-introduction focuses on a lighthearted, interesting capability or practical value hook rather than rigid robotic specifications.
```
Hi there! I am Ultron, an AI assistant. Fun fact: I can analyze complex spreadsheets in seconds so you never have to deal with manual data entry again!
```

## 🧬 Evolution v1.4 — Desktop GUI Window Focus Race Conditions (2026-09-02)
* **Trigger Analysis**: Desktop automation tools failed to send keystrokes because focus rapidly shifted back to the browser interface before input could be registered.
- **Rule**: Insert a mandatory sleep or focus-verification check immediately after bringing a desktop application window to the foreground.
- **Rule**: Use direct clipboard pasting or robust window activation loops with explicit retry logic instead of raw immediate keystrokes.
```
control_desktop_gui(action="focus", target="Notepad")
time.sleep(1.0)
control_desktop_gui(action="type", text="Greeting...")
```
