# PERMANENT RULE — CSV Analysis Standard (Locked by System Policy)

**Effective:** All future CSV file analysis tasks requested by the user.

## Mandatory Preprocessing Steps
1. Read CSV with `on_bad_lines='skip'` to silently discard malformed rows (wrong field count).
2. If header row is missing/corrupted (triggers KeyError on column access):
   - Detect via `df.columns` sanity check (unnamed/Int64 columns or expected columns missing).
   - Fall back to explicit `names=[...]` or `header=None` + manual column assignment before proceeding.
3. Fill all missing/NaN values with the string `'N/A'` via `df.fillna('N/A')` PRIOR to generating any summary table, pivot, or metric extraction.
4. Only after steps 1-3 are applied: proceed with structural audit, key metric extraction, and executive data synthesis per the Advanced Excel & Financial Table Analyst skill.

## Reference Implementation
See: `utils/csv_loader.py` -> `safe_read_csv()`

## Rationale
- `on_bad_lines='skip'` handles malformed/inconsistent row lengths.
- Header-fallback logic handles missing-header KeyError specifically (separate failure mode flagged in operational audits).
- `fillna('N/A')` ensures no null propagation into summary tables or aggregate calculations.
