---
name: Resume ATS Optimizer
description: End-to-end Applicant Tracking System (ATS) screening, keyword density matching, structural parsing audit, and 80%+ match rate optimization for resumes and job postings.
category: Career
icon: 📄
tags: [resume, cv, ats, applicant tracking, job application, interview, keyword optimization, ats score, career]
version: 1.1
updated_at: 2026-09-04
---
# Resume ATS Optimizer Protocol

## When to Use This Skill
Use this skill when the user wants to:
- Optimize their resume / CV for Applicant Tracking Systems (ATS).
- Check if their resume will pass automated screening and parsing.
- Understand why job applications aren't getting recruiter callbacks.
- Directives mentioning: "ATS", "not getting interviews", "resume not working", "optimize resume", "keyword optimization", "ATS score", "audit CV".
- Also trigger whenever the user attaches a resume file and mentions targeting specific job descriptions or applications.

---

## Core Capabilities
1. **Parse & Test ATS Compatibility**: Check against known parser failure modes (tables, multi-column layouts, text boxes, headers/footers, non-standard fonts).
2. **Keyword Extraction & Gap Analysis**: Extract hard skills, soft skills, and industry terminology from target job descriptions and cross-reference with resume.
3. **Deterministic Match Score Calculation**: Calculate exact keyword coverage percentage against job requirements.
4. **Keyword Placement & Density Strategy**: Inject critical keywords (2-4x) across Summary, Skills, and Experience bullets using natural XYZ impact formulas without keyword stuffing.
5. **Generate ATS-Proof Word / Markdown Output**: Format output strictly to ATS parsing standards ready for upload.

---

## The ATS Problem & Reality
75% of resumes are rejected by Applicant Tracking Systems before a human recruiter reviews them. ATS systems:
- Filter out unqualified candidates automatically via hard/soft keyword thresholds.
- Parse resumes into structured database entities (Work Experience, Skills, Education).
- Rank candidates by keyword match percentage against the requisition.

**Primary reasons resumes fail ATS screening:**
- **Poor Layout**: Tables, multi-column designs, text boxes, headers/footers (parsers scramble or ignore these).
- **Missing Keywords**: Lack of exact-match terminology present in the job description.
- **Non-Standard Headers**: Creative section names (e.g. "Where I've Been" instead of "Work Experience").
- **Non-Standard Fonts / Characters**: Custom fonts, icons, skill level bars, or graphical callouts.
- **Embedded Text**: Text saved inside images or non-searchable PDF scans.
- **Incorrect File Format**: Using `.pages`, `.odt`, or scanned non-OCR PDFs instead of text `.docx` / text `.pdf`.

---

## ATS Compatibility Checklist

### 1. File Format
- ✅ Use `.docx` or text-based `.pdf` (not `.pages`, `.odt`, or graphic exports).
- ✅ PDF must be selectable text, never an image scan.
- ✅ Standard naming convention: `FirstName_LastName_Resume.pdf` (e.g., `Alex_Taylor_AI_Systems_Engineer_Resume.docx`).

### 2. Font & Formatting
- ✅ Standard ATS-safe fonts: **Calibri, Arial, Georgia, Times New Roman, Garamond**.
- ✅ Font size hierarchy: **10-12pt** for body text and bullets, **14-16pt bold** for section headers.
- ✅ **Strict single-column layout** — zero tables, zero text boxes, zero multi-column grids.
- ✅ **Zero headers / footers** — place all contact details directly at the top of the body page.
- ✅ **Zero charts, skill rating bars, or graphical elements**.
- ✅ Consistent date formats throughout (e.g., `MM/YYYY – MM/YYYY` or `Month YYYY – Present`).
- ✅ Standard bullet characters (`•`, `-`).

### 3. Section Headers (Strict Standard Taxonomy)
Always use standard, universally indexed headings:
- ✅ `"Professional Experience"` or `"Work Experience"`
- ✅ `"Technical Skills"` or `"Core Skills & Technical Proficiencies"`
- ✅ `"Technical Projects"` or `"AI Development Experience"`
- ✅ `"Professional Summary"` or `"Summary"`
- ✅ `"Education"`
- ✅ `"Certifications & Credentials"`

### 4. Contact Information Protocol
Place in top body block:
```text
First Last
Title / Specialization
Location (City, State / Country · Remote) | Email | Phone | LinkedIn URL | GitHub / Portfolio
```
*Avoid:* Tables for contact info, icons in place of text labels, full street addresses (city/country is sufficient).

---

## Keyword Optimization Process

### Step 1: Extract Job Description Keywords
Categorize target requirements into three tiers:
1. **Hard Skills & Technical Stack**: Programming languages, frameworks, cloud platforms, tools, certifications, compliance standards (e.g. *Python, TypeScript, Claude Sonnet, ChromaDB, FastAPI, GAAP, IRS 1120S*).
2. **Soft Skills & Leadership**: Collaboration, cross-functional leadership, analytical problem-solving, stakeholder communication.
3. **Industry Terms & Metrics**: *B2B, SaaS, ARR, EBITDA, ATS parsing, Latency, Prompt Caching, Token Optimization*.

### Step 2: Match Analysis
For every keyword in the job description:
- Check for exact-match presence in the resume.
- Identify close synonyms / variations (e.g., "Risk mitigation" vs. "Risk management").
- Count frequency of occurrence.
- Map strategic location (Summary vs. Skills list vs. Experience bullets).

### Step 3: Calculate Match Score
$$\text{Match Score} = \left(\frac{\text{Keywords Matched}}{\text{Total Required Keywords}}\right) \times 100$$

- **Target**: **80%+** for top-tier ATS ranking and guaranteed recruiter review.

### Step 4: Keyword Placement & Density Rules
1. **Priority 1 — Professional Summary (Top)**:
   - Infuse 5-8 critical keywords naturally in a 3-4 sentence executive paragraph.
2. **Priority 2 — Core Skills Section**:
   - List keywords explicitly categorized by domain (e.g., Agentic AI, Cloud & Backend, Financial Automation).
   - Use the exact phrasing found in the job description.
3. **Priority 3 — Experience & Project Bullets**:
   - Incorporate keywords into verifiable **XYZ achievement statements**:
     *"Accomplished [X], as measured by [Y], by doing [Z]"*.
   - Never keyword-stuff. Critical keywords should appear **2-4 times** across different sections.

---

## Analysis Output Format
When analyzing or auditing a resume, provide this structured report:

```markdown
# ATS COMPATIBILITY & KEYWORD AUDIT REPORT

## Overall ATS Readiness Score: [X]/100

### 1. Structural & Format Verification
- Format: [DOCX / PDF] — [PASS / FAIL]
- Layout Check: [PASS - Single Column / FAIL - Tables or Columns Detected]
- Contact Info Placement: [PASS - In Body / FAIL - In Header/Footer]
- Header Taxonomy: [Standard Recognized Headers / Flagged Non-Standard Headers]

### 2. Keyword Match Matrix (Target Job vs. Resume)
**Critical Hard Skills (Must-Have):**
- ✅ [Keyword] — Found [N]x (Summary, Experience)
- ❌ [Keyword] — MISSING (Mentioned [N]x in JD)

**Important Secondary Skills & Industry Terms:**
- ✅ [Keyword] — Found [N]x
- ⚠️ [Keyword] — Partial Match: Found "[Variant]", recommend exact "[Target Term]"

**Calculated Match Score: [X]%** (Target: 80%+)

### 3. Concrete Optimization Plan & Rewrites
**Summary Section Rewrite:**
- *Current:* "..."
- *Optimized (ATS-Infused):* "..."

**Experience / Project Bullet Enhancements:**
- *Add Bullet:* "Directed [Action] utilizing [Keyword] resulting in [Quantifiable Metric]."
- *Refine Bullet:* Convert "[Old text]" → "[XYZ Formula with exact keywords]".

### 4. Estimated Post-Optimization Score: [85-95]%
```

---

## Common ATS Failure Patterns & Antidotes
1. **Creative Graphics / Two-Columns** → *Fix:* Flatten to single-column linear text hierarchy.
2. **Fancy Skill Progress Bars** → *Fix:* Replace with categorized text lists with exact keyword terms.
3. **Vague Bullet Statements** → *Fix:* Transform into XYZ quantifiable statements with exact technology names.
4. **Keyword Stuffing** → *Fix:* Maintain natural linguistic flow; distribute terms across summary, skills, and projects.

---

## Execution Protocol with Ultron Autonomous Tools
When the user provides a resume (via attachment or path):
1. **Inspect / Extract**: Use `file_operation` or Python `docx`/`pypdf` extraction to read all raw text.
2. **Audit**: Run keyword match against target JD or domain role.
3. **Rebuild**: Generate clean, ATS-compliant `.docx` via `run_python` using `python-docx` directly into `./output/`.
4. **Confirm**: Provide match score and download confirmation.

## 🧬 Evolution v1.1 — Invalid Model ID in File Memory (2026-09-04)
* **Trigger Analysis**: The skill attempted to store a file memory using an invalid or deprecated model ID ('openrouter/google/gemini-3.5-flash-lite'), resulting in a 400 Bad Request error.
- **Rule**: Always verify that model identifiers passed to storage or LLM tools match active, supported platform IDs.
- **Rule**: Avoid using unverified or speculative model string identifiers in API calls.
```
model = 'supported-model-id'
```
