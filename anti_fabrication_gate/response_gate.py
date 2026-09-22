"""
response_gate.py — Structural anti-fabrication gate (v2).

Changes vs v1
-------------
* gate_response() now also calls check_scope_claims() (Fix 3).
  Any response claiming a dataset count that doesn't match the
  ledger-recorded actual count is rejected with the same GateRejection
  mechanism as fabricated evidence blocks.

gate_response(response_text, ledger) -> str | GateRejection

Must be called UNCONDITIONALLY as the last step before any response
reaches the user.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Sequence

from evidence_ledger import EvidenceLedger, LedgerEntry
from scope_integrity import check_scope_claims, ScopeViolation


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class GateRejection:
    """
    Returned instead of the response when fabrication or scope mismatch
    is detected. The pipeline MUST NOT deliver original response_text.
    """
    reason:           str
    flagged_blocks:   list[str] = field(default_factory=list)
    missing_tokens:   list[str] = field(default_factory=list)
    scope_violations: list[ScopeViolation] = field(default_factory=list)

    def __str__(self) -> str:
        parts = [f"GateRejection: {self.reason}"]
        if self.missing_tokens:
            tokens = ", ".join(self.missing_tokens[:10])
            parts.append(
                f"Missing tokens not found in any ledger entry: [{tokens}]"
            )
        if self.flagged_blocks:
            blocks_preview = "\n---\n".join(b[:200] for b in self.flagged_blocks)
            parts.append(f"Flagged block(s):\n{blocks_preview}")
        if self.scope_violations:
            parts.append("Scope violations:")
            for v in self.scope_violations:
                parts.append(f"  {v}")
        return "\n".join(parts)


# ---------------------------------------------------------------------------
# Pattern library (unchanged from v1)
# ---------------------------------------------------------------------------

_RE_JSON_FENCE = re.compile(
    r"```(?:json|JSON)\s*\n(.*?)```",
    re.DOTALL,
)

_RE_TERMINAL_BLOCK = re.compile(
    r"(?:^|\n)((?:[ \t]*(?:>>>|<<<|\[(?:PASS|FAIL|NODE|INFO|WARN|ERR)\b|"
    r"Usage:|CompletionUsage|VERIFIED|status:|verified:|passed:|result:)"
    r"[^\n]*\n?){2,})",
    re.MULTILINE | re.IGNORECASE,
)

_RE_INLINE_STATUS = re.compile(
    r'"(?:status|verified|passed|result|value|exit_code)"\s*:\s*'
    r'(?:"[^"]*"|-?\d+(?:\.\d+)?|true|false|null)',
    re.IGNORECASE,
)

_RE_NUMERIC   = re.compile(r"-?\d+(?:\.\d+)?")
_RE_QUOTED    = re.compile(r'"([^"]{2,})"')
_RE_STATUS_KW = re.compile(
    r"\b(ok|pass(?:ed)?|fail(?:ed)?|verified|true|false|error|success)\b",
    re.IGNORECASE,
)

_EVIDENCE_KEYS = {
    "status", "verified", "passed", "result", "value",
    "exit_code", "stdout", "output", "score", "total",
}


# ---------------------------------------------------------------------------
# Helpers (unchanged from v1)
# ---------------------------------------------------------------------------

def _is_evidence_json(block: str) -> bool:
    lower = block.lower()
    return any(f'"{k}"' in lower for k in _EVIDENCE_KEYS)


def _extract_critical_tokens(block: str) -> list[str]:
    tokens: list[str] = []
    tokens.extend(_RE_NUMERIC.findall(block))
    tokens.extend(m.group(1) for m in _RE_QUOTED.finditer(block))
    tokens.extend(_RE_STATUS_KW.findall(block))
    seen: set[str] = set()
    result: list[str] = []
    for t in tokens:
        t_lower = t.lower()
        if t_lower not in seen and t_lower not in {"0", "1", "true", "false", "null"}:
            seen.add(t_lower)
            result.append(t)
    return result


def _token_in_any_entry(token: str, entries: Sequence[LedgerEntry]) -> bool:
    for entry in entries:
        if token in entry.raw_stdout or token in entry.raw_stderr:
            return True
    return False


def _find_evidence_blocks(response_text: str) -> list[str]:
    blocks: list[str] = []

    for m in _RE_JSON_FENCE.finditer(response_text):
        content = m.group(1).strip()
        if _is_evidence_json(content):
            blocks.append(content)

    for m in _RE_TERMINAL_BLOCK.finditer(response_text):
        block = m.group(1).strip()
        if len(block) > 20:
            blocks.append(block)

    for m in _RE_INLINE_STATUS.finditer(response_text):
        snippet = m.group(0)
        already = any(snippet in b for b in blocks)
        if not already:
            blocks.append(snippet)

    return blocks


# ---------------------------------------------------------------------------
# The gate (v2 — adds scope check)
# ---------------------------------------------------------------------------

def gate_response(
    response_text: str,
    ledger: EvidenceLedger,
) -> str | GateRejection:
    """
    Gate every response before it reaches the user.

    Checks (in order):
    1. Evidence blocks — must trace verbatim to ledger tool entries
    2. Scope claims   — "processed N items" must match ledger scope entries

    Returns
    -------
    str             — original response_text unchanged if all checks pass
    GateRejection   — if any check fails
    """
    all_flagged_blocks:  list[str]          = []
    all_missing_tokens:  list[str]          = []
    all_scope_violations: list[ScopeViolation] = []

    # ── Check 1: Evidence blocks ─────────────────────────────────────────
    evidence_blocks = _find_evidence_blocks(response_text)
    if evidence_blocks:
        entries = list(ledger.all_entries.values())
        for block in evidence_blocks:
            critical = _extract_critical_tokens(block)
            if not critical:
                if not entries:
                    all_flagged_blocks.append(block)
                continue
            missing = [
                tok for tok in critical
                if not _token_in_any_entry(tok, entries)
            ]
            if missing:
                all_flagged_blocks.append(block)
                all_missing_tokens.extend(missing)

    # ── Check 2: Scope integrity (Fix 3) ─────────────────────────────────
    scope_violations = check_scope_claims(response_text, ledger)
    all_scope_violations.extend(scope_violations)

    # ── Decision ─────────────────────────────────────────────────────────
    if all_flagged_blocks or all_scope_violations:
        reasons = []
        if all_flagged_blocks:
            reasons.append(
                "Evidence block(s) found whose critical tokens do not appear "
                "verbatim in any real ledger entry for this turn."
            )
        if all_scope_violations:
            reasons.append(
                "Dataset count claim(s) in response do not match ledger-recorded "
                "actual row/item counts."
            )
        return GateRejection(
            reason=" | ".join(reasons),
            flagged_blocks=all_flagged_blocks,
            missing_tokens=all_missing_tokens,
            scope_violations=all_scope_violations,
        )

    return response_text
