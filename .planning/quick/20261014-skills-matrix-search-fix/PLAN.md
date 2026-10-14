---
status: complete
date: 2026-10-14
slug: skills-matrix-search-fix
---

# Quick Task: Fix Skills Matrix Search Bar and Multi-Field Filtering

## Objective
Fix the broken search bar in the Ultron Skills Matrix modal (`SkillsModal.tsx`):
1. Resolve layout flex squish bug where the search bar was compressed into an inoperable ~40px circle next to horizontal category filter chips.
2. Provide a prominent, full-width dedicated search bar with instant visual feedback, clear button, match counter, and escape-key handling.
3. Enhance search filtering logic to match across all skill properties (name, description, id/skill_id, category, tags, and instructions) with multi-token support.
4. Add cross-category match suggestions so users can quickly navigate across categories when searching.
5. Rebuild production assets to `static/` and verify with automated end-to-end integration tests.
