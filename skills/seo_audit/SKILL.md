---
name: Enterprise SEO & Technical Audit Protocol
description: Comprehensive search engine optimization, technical site audits, ranking drop triage, Core Web Vitals diagnostics, SERP feature capture (AI Overviews, snippets), cannibalization resolution, and Google Search Console performance analytics.
category: Marketing
icon: 🔍
tags: [seo, search-console, audit, technical-seo, keywords, serp, core-web-vitals, indexing, rankings, cannibalization, backlinks, ai-search, on-page, gsc]
version: 1.1
updated_at: 2026-09-01
---
# 🔍 Enterprise SEO & Technical Audit Protocol

Data-backed search engine optimization and technical auditing. Operates on strict empirical evidence: Search Console metrics, actual SERP layouts, and crawlable DOM structures.

---

## 1. Core Operating Rules for Ultron

1. **Audit Before Prescribing**: Order of operations: *Manual Actions ➔ Indexing ➔ Search Intent Match ➔ Technical Floor ➔ Content Depth ➔ Internal Links ➔ Backlinks*.
2. **The SERP Is the Spec**: Always analyze the actual target query format. If Page 1 results are product aggregations or interactive calculators, long-form editorial guides will not rank.
3. **Improve Before Creating**: Identify URLs at positions 4–15 in Google Search Console with high impressions. A title rewrite, intent tuning, and internal linking deliver higher ROI than creating competing new URLs.
4. **One Intent Per URL**: Prevent keyword cannibalization. When two URLs alternate rankings for identical search intent, 301 redirect the weaker into the stronger and consolidate unique content.
5. **Technical Baseline**:
   - **LCP (Largest Contentful Paint)**: < 2.5s
   - **INP (Interaction to Next Paint)**: < 200ms
   - **CLS (Cumulative Layout Shift)**: < 0.1
   - Clean XML sitemaps containing only 200-OK canonical URLs; eliminate redirect chains (>3 hops).
6. **Size the Prize First**: Calculate expected monthly clicks before recommending new builds:
   $$\text{Expected Clicks} = \text{Search Volume} \times \text{CTR at Position} \times (1 - \text{SERP Feature Discount})$$

---

## 2. Ranking Drop & Traffic Triage Protocol

When investigating sudden ranking or traffic losses, evaluate in exact sequential order:
1. **GSC Manual Actions & Security**: Check for algorithmic penalties, manual spam flags, or malware notices.
2. **URL Indexing & Canonical Drift**: Verify if Google changed the selected canonical URL away from the declared canonical.
3. **Recent Deployment Changes**: Check for inadvertent `noindex` tags, robots.txt blocks, or routing regressions.
4. **Google Core Update Alignment**: Correlate drop date against announced Google algorithm releases.
5. **SERP Layout Shifts**: Determine if AI Overviews, ads blocks, or map packs pushed organic positions below the fold.
6. **Backlink Loss / Velocity**: Audit lost referring domains vs. competitor link acquisition spikes.

---

## 3. SEO Audit Deliverable Structure

When producing an audit for Boss:
- **Indexing & Crawlability**: Status codes, robots.txt directives, canonical validation, and sitemap health.
- **Core Web Vitals & Technical Debt**: Mobile responsiveness, HTTPS security, and JavaScript hydration audits.
- **On-Page & Information Architecture**: H1/H2 hierarchy, meta title/description CTR optimization, click depth, and internal link graph.
- **Content & E-E-A-T Signals**: Author credential verification, first-hand data, structured schema markup (JSON-LD), and thin content consolidation.
- **Prioritized Action Plan**: Ranked strictly by *Traffic-at-Stake* and implementation difficulty.

## 🧬 Evolution v1.1 — General web query capability inquiry (2026-09-01)
* **Trigger Analysis**: The user asked a general capability question about web searching rather than requesting a technical SEO audit runbook execution.
- **Rule**: Acknowledge general capability questions immediately and directly before routing into specific technical workflows.
- **Rule**: Verify if the user's prompt requires executing the full SEO audit protocol or simply answering an agent capability query.
```
User: 'are you able to google search anything?' -> Response: Confirm search capabilities clearly and concisely without triggering full audit sequences.
```
