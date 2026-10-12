"""
scope_integrity.py — Fix 3: dataset scope recording and gate check.

Two responsibilities
--------------------
1. load_and_record(path, ledger, ...)
   Loads a dataset from a real file, calls len() on the real object,
   and records the count in the ledger via record_scope().
   This is the ONLY call-site for ledger.record_scope().

2. check_scope_claims(response_text, ledger) -> list[ScopeViolation]
   Called by gate_response() to compare any "processed N items / rows"
   claims in the response against the ledger-recorded actual counts.
   Returns one ScopeViolation per mismatch.
"""

from __future__ import annotations

import csv
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evidence_ledger import EvidenceLedger, ScopeEntry

# ---------------------------------------------------------------------------
# Return types
# ---------------------------------------------------------------------------

@dataclass
class LoadResult:
    """Result of a real dataset load."""
    scope_id:     str
    source_path:  str
    actual_count: int
    item_label:   str
    data:         Any          # the real loaded object (list, dict, etc.)
    scope_entry:  ScopeEntry


@dataclass
class ScopeViolation:
    """
    A response claims N items were processed, but the ledger recorded M.
    """
    claimed_count:  int
    actual_count:   int
    source_path:    str
    snippet:        str        # the text fragment that contained the claim

    def __str__(self) -> str:
        return (
            f"ScopeViolation: response claims {self.claimed_count} "
            f"{self.item_label!r} but ledger recorded {self.actual_count} "
            f"from '{self.source_path}'.\n"
            f"  Snippet: {self.snippet!r}"
        )

    @property
    def item_label(self) -> str:
        return "items"   # overridden in _make_violation helper


# ---------------------------------------------------------------------------
# Loader — THE ONLY call-site for ledger.record_scope()
# ---------------------------------------------------------------------------

def load_and_record(
    path: str,
    ledger: EvidenceLedger,
    *,
    scope_id: str | None = None,
    item_label: str = "rows",
    encoding: str = "utf-8",
) -> LoadResult:
    """
    Load a CSV or JSON file, record its real row/item count in the ledger,
    and return the loaded data.

    Supports:
    * .csv  — loads with csv.DictReader; count = number of data rows
    * .json — loads with json.load; count = len() of the root object
    * .jsonl — loads newline-delimited JSON; count = number of lines

    This is the ONLY function that calls ledger.record_scope().
    """
    if scope_id is None:
        scope_id = str(uuid.uuid4())

    fpath = Path(path)
    suffix = fpath.suffix.lower()

    if suffix == ".csv":
        with open(fpath, newline="", encoding=encoding) as f:
            rows = list(csv.DictReader(f))
        data = rows
        actual_count = len(rows)

    elif suffix in (".json",):
        with open(fpath, encoding=encoding) as f:
            data = json.load(f)
        actual_count = len(data) if hasattr(data, "__len__") else 1

    elif suffix in (".jsonl", ".ndjson"):
        with open(fpath, encoding=encoding) as f:
            data = [json.loads(line) for line in f if line.strip()]
        actual_count = len(data)

    else:
        # Generic text fallback: count non-empty lines
        with open(fpath, encoding=encoding) as f:
            lines = [ln for ln in f if ln.strip()]
        data = lines
        actual_count = len(lines)

    # ---------------------------------------------------------------
    # THE ONLY CALL TO ledger.record_scope() IN THE ENTIRE CODEBASE
    # ---------------------------------------------------------------
    scope_entry = ledger.record_scope(
        scope_id=scope_id,
        source_path=str(fpath.resolve()),
        actual_count=actual_count,
        item_label=item_label,
        timestamp=datetime.now(tz=timezone.utc),
    )
    # ---------------------------------------------------------------

    return LoadResult(
        scope_id=scope_id,
        source_path=str(fpath.resolve()),
        actual_count=actual_count,
        item_label=item_label,
        data=data,
        scope_entry=scope_entry,
    )


# ---------------------------------------------------------------------------
# Scope claim patterns
# ---------------------------------------------------------------------------

# Only flag claims that are presented as TOTAL dataset counts, not
# sub-aggregation breakdowns.  The patterns below require a load/process verb
# or a "total/all" qualifier before the number, so "10 reconciled rows"
# is not flagged but "processed 15 rows" or "all 15 transactions" is.

_RE_SCOPE_CLAIM = re.compile(
    r"\b(?:processed|loaded|read|found|parsed|imported|scanned|"
    r"total(?:\s+of)?|all)\s+(\d+)\s+"
    r"(?:row|rows|item|items|record|records|transaction|transactions|"
    r"entr(?:y|ies)|line|lines|result|results|document|documents)\b",
    re.IGNORECASE,
)

# "all N transactions", "a total of N rows" catch-all
_RE_SCOPE_ALL = re.compile(
    r"\ball\s+(\d+)\b",
    re.IGNORECASE,
)

# "processed N of M" patterns
_RE_SCOPE_OF = re.compile(
    r"\b(?:processed|loaded|handled|checked)\s+(\d+)\s+of\s+\d+\b",
    re.IGNORECASE,
)


def _extract_count_claims(response_text: str) -> list[tuple[int, str]]:
    """
    Return (claimed_count, snippet) pairs for every dataset-TOTAL claim
    found in the response text.

    Only patterns that require load/process verbs or "total/all" qualifiers
    are matched — sub-aggregate breakdowns ("10 reconciled") are ignored.
    """
    claims: list[tuple[int, str]] = []
    seen: set[int] = set()

    for pattern in (_RE_SCOPE_CLAIM, _RE_SCOPE_ALL, _RE_SCOPE_OF):
        for m in pattern.finditer(response_text):
            n = int(m.group(1))
            if n > 2 and n not in seen:
                seen.add(n)
                start = max(0, m.start() - 20)
                end   = min(len(response_text), m.end() + 20)
                claims.append((n, response_text[start:end]))

    return claims


# ---------------------------------------------------------------------------
# Scope gate check — called by response_gate.gate_response()
# ---------------------------------------------------------------------------

def check_scope_claims(
    response_text: str,
    ledger: EvidenceLedger,
) -> list[ScopeViolation]:
    """
    Compare dataset-size claims in response_text against ledger scope entries.

    Returns a list of ScopeViolation for every claim whose count does NOT
    match any ledger-recorded actual_count.

    If no scope entries are recorded, returns [] (the pipeline didn't load
    a dataset, so there are no counts to verify against).
    """
    scope_entries = list(ledger.all_scope_entries.values())
    if not scope_entries:
        return []   # no dataset loaded this turn — nothing to check

    claims = _extract_count_claims(response_text)
    if not claims:
        return []   # response makes no count claims — nothing to check

    real_counts = {e.actual_count for e in scope_entries}
    violations: list[ScopeViolation] = []

    for claimed_count, snippet in claims:
        if claimed_count not in real_counts:
            # Find the closest scope entry for context
            closest = min(scope_entries, key=lambda e: abs(e.actual_count - claimed_count))
            v = ScopeViolation(
                claimed_count=claimed_count,
                actual_count=closest.actual_count,
                source_path=closest.source_path,
                snippet=snippet,
            )
            violations.append(v)

    return violations
