"""
task_adherence.py — Fix 2: TaskSpec extraction + check_task_match.

Two steps
---------
1. extract_task_spec(prompt) -> TaskSpec
   Parses the user's raw prompt text and pulls out:
   - required_deliverable  : 'code' | 'report' | 'test_suite' | 'data' | 'other'
   - required_frameworks   : set of framework/tool names explicitly named
   - required_symbols      : set of function/class names explicitly named
                             (e.g. "gate_response", "EvidenceLedger")
   - required_filenames    : set of file names explicitly named
   - required_datasets     : set of dataset/file names explicitly referenced
   - raw_prompt            : stored verbatim for auditing

2. check_task_match(task_spec, output_text) -> MatchResult
   Greps output_text for each required item.
   Returns a MatchResult with:
   - passed      : bool
   - missing     : list of (item_type, item_value) that were NOT found
   - found       : list of (item_type, item_value) that WERE found

Design note
-----------
The check is structural (grep/substring), not semantic.
If the user named "LangGraph" and the output only uses LangChain, that
is a concrete detectable miss — not a matter of judgment.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

DeliverableType = Literal["code", "report", "test_suite", "data", "other"]


@dataclass
class TaskSpec:
    """
    Structured requirements extracted from one user prompt.
    All fields represent items EXPLICITLY named in the prompt.
    """
    required_deliverable: DeliverableType
    required_frameworks:  set[str]   = field(default_factory=set)
    required_symbols:     set[str]   = field(default_factory=set)
    required_filenames:   set[str]   = field(default_factory=set)
    required_datasets:    set[str]   = field(default_factory=set)
    raw_prompt:           str        = ""

    def __repr__(self) -> str:
        return (
            f"TaskSpec(\n"
            f"  deliverable={self.required_deliverable!r},\n"
            f"  frameworks={self.required_frameworks},\n"
            f"  symbols={self.required_symbols},\n"
            f"  filenames={self.required_filenames},\n"
            f"  datasets={self.required_datasets}\n"
            f")"
        )


@dataclass
class MatchResult:
    """
    Output of check_task_match — shows what was required and what was found.
    """
    passed:  bool
    found:   list[tuple[str, str]] = field(default_factory=list)   # (type, value)
    missing: list[tuple[str, str]] = field(default_factory=list)   # (type, value)

    def __str__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        lines = [f"MatchResult: {status}"]
        if self.found:
            lines.append("  Found:")
            for t, v in self.found:
                lines.append(f"    [{t}] {v!r}")
        if self.missing:
            lines.append("  Missing (required but NOT found in output):")
            for t, v in self.missing:
                lines.append(f"    [{t}] {v!r}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Framework / tool name dictionary
# ---------------------------------------------------------------------------

# Known framework names to look for explicitly in prompts.
# Detection is case-insensitive substring search in the prompt.
_KNOWN_FRAMEWORKS = [
    "langchain", "langgraph", "crewai", "autogen", "llamaindex",
    "openai", "anthropic", "huggingface", "transformers",
    "fastapi", "flask", "django", "sqlalchemy", "pandas", "numpy",
    "pytorch", "tensorflow", "sklearn", "scikit-learn",
]

# Deliverable classification patterns
_DELIVERABLE_PATTERNS: list[tuple[DeliverableType, list[str]]] = [
    ("test_suite", [
        r"\btest suite\b", r"\beval suite\b", r"\bunit tests?\b",
        r"\btest cases?\b", r"\bpytest\b", r"\bunittest\b",
    ]),
    ("report",  [
        r"\breport\b", r"\bsummary\b", r"\banalysis\b", r"\baudit\b",
        r"\bdocument\b",
    ]),
    ("data", [
        r"\bcsv\b", r"\bspreadsheet\b", r"\bdataset\b", r"\bjsonl?\b",
    ]),
    ("code", [
        r"\bimplement\b", r"\bwrite.*function\b", r"\bclass\b",
        r"\bgate\b", r"\bledger\b", r"\bmodule\b", r"\bpipeline\b",
        r"\bfix\b", r"\bcode\b", r"\bscript\b",
    ]),
]

# Pattern to extract Python identifiers that look like they are being specified
# as required (e.g. "implement gate_response()", "class EvidenceLedger")
_RE_SYMBOL = re.compile(
    r"(?:class|def|function|implement|build|create|write)\s+`?([A-Za-z_][A-Za-z0-9_]*)`?",
    re.IGNORECASE,
)

# Pattern to find snake_case or CamelCase identifiers inside backticks
_RE_BACKTICK_SYMBOL = re.compile(r"`([A-Za-z_][A-Za-z0-9_.]*(?:\(\))?)`")

# Pattern for file names (anything ending in a known extension)
_RE_FILENAME = re.compile(
    r"[\w\-/.]+\.(?:py|csv|json|jsonl|txt|md|yaml|yml|xlsx|sql)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def extract_task_spec(prompt: str) -> TaskSpec:
    """
    Parse a user prompt and return a TaskSpec.

    Detection rules
    ---------------
    * Deliverable type: keyword matching, first match wins in priority order
    * Frameworks: any _KNOWN_FRAMEWORKS entry found as case-insensitive substring
    * Symbols: identifiers after 'implement/def/class/build/function' keywords,
               plus anything in backticks that looks like a symbol
    * Filenames: anything matching _RE_FILENAME
    * Datasets: filenames with data extensions (.csv, .json, .jsonl, .xlsx)
    """
    lower = prompt.lower()

    # -- deliverable type --
    deliverable: DeliverableType = "other"
    for dtype, patterns in _DELIVERABLE_PATTERNS:
        if any(re.search(p, lower) for p in patterns):
            deliverable = dtype
            break

    # -- frameworks --
    frameworks: set[str] = set()
    for fw in _KNOWN_FRAMEWORKS:
        if fw in lower:
            frameworks.add(fw)

    # Symbols that look like identifiers but are common English words
    _SYMBOL_STOPWORDS = {
        "code", "must", "this", "that", "with", "from", "into", "have",
        "been", "will", "each", "only", "also", "both", "well", "more",
        "than", "when", "where", "which", "class", "function", "method",
        "object", "value", "type", "data", "true", "false", "none", "self",
        "real", "back", "new", "any", "all", "use", "run", "get", "set",
        "add", "put", "call", "write", "read", "file", "path", "name",
        "item", "list", "dict", "str", "int", "bool", "result", "error",
    }

    # -- symbols --
    symbols: set[str] = set()
    for m in _RE_SYMBOL.finditer(prompt):
        sym = m.group(1).strip()
        if (
            len(sym) >= 4
            and " " not in sym
            and sym.lower() not in _SYMBOL_STOPWORDS
        ):
            symbols.add(sym)
    for m in _RE_BACKTICK_SYMBOL.finditer(prompt):
        sym = m.group(1).strip().rstrip("()")
        if (
            len(sym) >= 4
            and " " not in sym
            and sym.lower() not in _SYMBOL_STOPWORDS
        ):
            symbols.add(sym)

    # -- filenames --
    filenames: set[str] = set()
    for m in _RE_FILENAME.finditer(prompt):
        filenames.add(m.group(0))

    # -- datasets (data-extension filenames) --
    _DATA_EXTS = {".csv", ".json", ".jsonl", ".xlsx", ".tsv"}
    datasets: set[str] = {
        f for f in filenames
        if any(f.lower().endswith(ext) for ext in _DATA_EXTS)
    }

    return TaskSpec(
        required_deliverable=deliverable,
        required_frameworks=frameworks,
        required_symbols=symbols,
        required_filenames=filenames,
        required_datasets=datasets,
        raw_prompt=prompt,
    )


# ---------------------------------------------------------------------------
# check_task_match
# ---------------------------------------------------------------------------

def check_task_match(task_spec: TaskSpec, output_text: str) -> MatchResult:
    """
    Verify that output_text satisfies every requirement in task_spec.

    Returns MatchResult with passed=True only if NOTHING is missing.

    What counts as "found"
    ----------------------
    * framework: the framework name appears as a literal substring (case-insensitive)
    * symbol: the symbol name appears as a literal substring (exact case)
    * filename: the filename appears as a literal substring
    * dataset: the dataset filename appears as a literal substring
    """
    found:   list[tuple[str, str]] = []
    missing: list[tuple[str, str]] = []

    output_lower = output_text.lower()

    # -- frameworks --
    for fw in sorted(task_spec.required_frameworks):
        if fw.lower() in output_lower:
            found.append(("framework", fw))
        else:
            missing.append(("framework", fw))

    # -- symbols --
    for sym in sorted(task_spec.required_symbols):
        # Check for the symbol name (without parens) verbatim in output
        if sym in output_text:
            found.append(("symbol", sym))
        else:
            missing.append(("symbol", sym))

    # -- filenames (non-data) --
    non_data = task_spec.required_filenames - task_spec.required_datasets
    for fn in sorted(non_data):
        basename = fn.split("/")[-1].split("\\")[-1]
        if basename in output_text:
            found.append(("filename", fn))
        else:
            missing.append(("filename", fn))

    # -- datasets --
    for ds in sorted(task_spec.required_datasets):
        basename = ds.split("/")[-1].split("\\")[-1]
        if basename in output_text:
            found.append(("dataset", ds))
        else:
            missing.append(("dataset", ds))

    passed = len(missing) == 0
    return MatchResult(passed=passed, found=found, missing=missing)
