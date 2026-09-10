"""
skill_evolution.py — Ultron Autonomous Skill Mutation, Versioning & Evolution Engine.

Enables continuous self-healing of Ultron skills:
1. Tracks empirical usage metrics (successes, failures, reliability rates) in SQLite.
2. When a skill encounters a failure, edge case, or API limitation during a live turn,
   autonomously analyzes the discrepancy, patches the SKILL.md runbook with concrete
   corrective rules, bumps the semantic version (e.g. v1.0 -> v1.1), and records the
   mutation changelog.
3. Automatically triggers vector re-indexing so evolved rules are immediately active.
"""

from __future__ import annotations

import datetime
import json
import re
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SKILLS_DIR = Path(__file__).parent / "skills"
DATA_DIR = Path(__file__).parent / "data"
DB_PATH = DATA_DIR / "skill_evolution.db"

_MUTATION_PROMPT = """\
You are the ULTRON SKILL MUTATION & EVOLUTION ENGINE.
An existing Ultron skill runbook was executed during a task, but encountered an error, unexpected tool result, or suboptimal outcome.

YOUR OBJECTIVE:
Analyze the execution failure and produce a concise, production-grade patch to update the skill's instructions.
The patch must clearly state the newly learned edge case, the mistake to avoid, and the exact step-by-step procedure to follow next time.

SKILL BEING EVOLVED:
Skill ID: {skill_id}
Skill Name: {skill_name}

USER'S ORIGINAL DIRECTIVE:
{user_input}

SYSTEM TOOL ACTIONS & TERMINAL LOGS:
{tool_summary}

EVALUATION LESSON / REASON FOR FAILURE:
{failure_reason}

EXISTING SKILL INSTRUCTIONS:
{existing_instructions}

MUTATION RULES:
1. Identify the root cause of the breakdown (e.g. missing API parameter, wrong file path, unhandled edge case, incorrect assumption).
2. Formulate 1-3 crisp, deterministic rules or procedural adjustments that prevent this exact failure in future runs.
3. Output EXACTLY in this JSON format — no conversational text, no markdown backticks around the json:
{{
  "edge_case_title": "<Short 3-6 word title of the discovered edge case>",
  "root_cause_analysis": "<1 clear sentence explaining why the previous approach failed>",
  "corrective_rules": [
    "<Rule 1: Exact imperative instruction>",
    "<Rule 2: Optional additional guideline>"
  ],
  "example_snippet": "<Optional concrete command, code snippet, or parameter syntax to use>",
  "summary_of_changes": "<Brief changelog note for version history>"
}}
"""


@dataclass
class MutationRecord:
    skill_id: str
    from_version: str
    to_version: str
    trigger_reason: str
    edge_case_title: str
    diff_summary: str
    timestamp: str = ""
    id: int = 0


class SkillEvolutionDB:
    """
    Manages SQLite storage for skill version metadata, reliability metrics, and mutation changelogs.
    """

    def __init__(self, db_path: Path | str = DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS skill_metadata (
                    skill_id TEXT PRIMARY KEY,
                    version TEXT NOT NULL DEFAULT '1.0',
                    success_count INTEGER NOT NULL DEFAULT 0,
                    failure_count INTEGER NOT NULL DEFAULT 0,
                    last_score INTEGER DEFAULT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS mutation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    skill_id TEXT NOT NULL,
                    from_version TEXT NOT NULL,
                    to_version TEXT NOT NULL,
                    trigger_reason TEXT,
                    edge_case_title TEXT,
                    diff_summary TEXT,
                    patch_json TEXT,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (skill_id) REFERENCES skill_metadata (skill_id)
                );

                CREATE INDEX IF NOT EXISTS idx_mutations_skill ON mutation_history (skill_id);
            """)

    def get_or_create_metadata(self, skill_id: str, default_version: str = "1.0") -> dict[str, Any]:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM skill_metadata WHERE skill_id = ?", (skill_id,)).fetchone()
            if row:
                return dict(row)
            conn.execute(
                """INSERT INTO skill_metadata (skill_id, version, success_count, failure_count, created_at, updated_at)
                   VALUES (?, ?, 0, 0, ?, ?)""",
                (skill_id, default_version, now, now),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM skill_metadata WHERE skill_id = ?", (skill_id,)).fetchone()
            return dict(row) if row else {}

    def delete_skill_metadata(self, skill_id: str) -> None:
        """Deletes all metadata and mutation history for a deleted skill."""
        with self._get_conn() as conn:
            conn.execute("DELETE FROM mutation_history WHERE skill_id = ?", (skill_id,))
            conn.execute("DELETE FROM skill_metadata WHERE skill_id = ?", (skill_id,))
            conn.commit()

    def record_success(self, skill_id: str, score: int = 10) -> None:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.get_or_create_metadata(skill_id)
        with self._get_conn() as conn:
            conn.execute(
                """UPDATE skill_metadata 
                   SET success_count = success_count + 1, last_score = ?, updated_at = ?
                   WHERE skill_id = ?""",
                (score, now, skill_id),
            )
            conn.commit()

    def record_failure(self, skill_id: str, score: int = 4) -> None:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.get_or_create_metadata(skill_id)
        with self._get_conn() as conn:
            conn.execute(
                """UPDATE skill_metadata 
                   SET failure_count = failure_count + 1, last_score = ?, updated_at = ?
                   WHERE skill_id = ?""",
                (score, now, skill_id),
            )
            conn.commit()

    def record_mutation(
        self,
        skill_id: str,
        from_version: str,
        to_version: str,
        trigger_reason: str,
        edge_case_title: str,
        diff_summary: str,
        patch_json: str = "",
    ) -> int:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._get_conn() as conn:
            conn.execute(
                """UPDATE skill_metadata
                   SET version = ?, failure_count = failure_count + 1, updated_at = ?
                   WHERE skill_id = ?""",
                (to_version, now, skill_id),
            )
            cur = conn.execute(
                """INSERT INTO mutation_history 
                   (skill_id, from_version, to_version, trigger_reason, edge_case_title, diff_summary, patch_json, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (skill_id, from_version, to_version, trigger_reason, edge_case_title, diff_summary, patch_json, now),
            )
            conn.commit()
            return cur.lastrowid or 0

    def get_skill_stats(self, skill_id: str) -> dict[str, Any]:
        with self._get_conn() as conn:
            meta = conn.execute("SELECT * FROM skill_metadata WHERE skill_id = ?", (skill_id,)).fetchone()
            if not meta:
                return {"version": "1.0", "success_count": 0, "failure_count": 0, "reliability": 1.0, "mutations": 0}
            meta_dict = dict(meta)
            total = meta_dict["success_count"] + meta_dict["failure_count"]
            meta_dict["reliability"] = (
                round(meta_dict["success_count"] / total, 2) if total > 0 else 1.0
            )
            mut_count = conn.execute(
                "SELECT COUNT(*) as c FROM mutation_history WHERE skill_id = ?", (skill_id,)
            ).fetchone()
            meta_dict["mutations"] = mut_count["c"] if mut_count else 0
            return meta_dict

    def list_recent_mutations(self, limit: int = 10) -> list[dict[str, Any]]:
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT * FROM mutation_history ORDER BY id DESC LIMIT ?""", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]


class SkillMutator:
    """
    Autonomous skill mutation agent.
    Analyzes execution discrepancies, refines SKILL.md instructions, and increments version.
    """

    def __init__(
        self,
        claude: Any | None = None,
        haiku_model: str = "claude-haiku-4-5-20251001",
        gemini: Any | None = None,
        gemini_model: str = "gemini-3.5-flash",
        provider: str = "gemini",
        skills_dir: Path = SKILLS_DIR,
        db_path: Path | str = DB_PATH,
        skill_manager: Any | None = None,
    ) -> None:
        self._claude = claude
        self._haiku_model = haiku_model
        self._gemini = gemini
        self._gemini_model = gemini_model
        self.provider = provider
        self._skills_dir = Path(skills_dir)
        self._db = SkillEvolutionDB(db_path)
        self._skill_manager = skill_manager

    @property
    def db(self) -> SkillEvolutionDB:
        """Exposes the underlying SkillEvolutionDB instance."""
        return self._db

    def _bump_version(self, current_version: str) -> str:
        """Bumps semantic minor version (e.g. '1.0' -> '1.1', '1.9' -> '2.0')."""
        match = re.search(r"(\d+)\.(\d+)", current_version)
        if match:
            major, minor = int(match.group(1)), int(match.group(2))
            minor += 1
            if minor >= 10:
                major += 1
                minor = 0
            return f"{major}.{minor}"
        return "1.1"

    def _parse_skill_file(self, skill_path: Path) -> tuple[dict[str, str], str]:
        """Parses YAML frontmatter and body from a SKILL.md file."""
        if not skill_path.exists():
            return {}, ""
        content = skill_path.read_text(encoding="utf-8")
        frontmatter: dict[str, str] = {}
        body = content

        fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
        if fm_match:
            fm_text, body = fm_match.group(1), fm_match.group(2)
            for line in fm_text.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    frontmatter[k.strip()] = v.strip().strip("\"'")

        return frontmatter, body

    def evolve_skill(
        self,
        skill_id: str,
        failure_reason: str,
        user_input: str,
        tool_actions: list[dict[str, Any]] | None = None,
        lesson_text: str = "",
    ) -> MutationRecord | None:
        """
        Synthesizes a targeted mutation patch and updates the skill's SKILL.md.
        """
        skill_folder = self._skills_dir / skill_id
        skill_file = skill_folder / "SKILL.md"
        if not skill_file.exists():
            # Try finding skill by name or auto prefix
            matches = list(self._skills_dir.glob(f"*{skill_id}*"))
            if matches and (matches[0] / "SKILL.md").exists():
                skill_folder = matches[0]
                skill_file = skill_folder / "SKILL.md"
                skill_id = skill_folder.name
            else:
                print(f"  [SKILL MUTATOR] Target skill file not found: {skill_file}")
                return None

        # Load existing content and version
        meta = self._db.get_or_create_metadata(skill_id)
        current_version = meta.get("version", "1.0")
        frontmatter, existing_body = self._parse_skill_file(skill_file)
        if "version" in frontmatter:
            current_version = frontmatter["version"]

        skill_name = frontmatter.get("name", skill_id.replace("_", " ").title())

        # Format tool summary
        tool_lines = []
        if tool_actions:
            for a in tool_actions[:6]:
                status = "SUCCESS" if a.get("success") else "FAILED"
                out = str(a.get("output", "") or a.get("error", ""))[:250]
                tool_lines.append(f"• Tool {a.get('tool')} [{status}]: {out}")
        tool_summary = "\n".join(tool_lines) if tool_lines else "No tool actions executed"

        prompt = _MUTATION_PROMPT.format(
            skill_id=skill_id,
            skill_name=skill_name,
            user_input=user_input[:800],
            tool_summary=tool_summary,
            failure_reason=f"{failure_reason}\nLesson: {lesson_text}",
            existing_instructions=existing_body[:2000],
        )

        raw = ""
        raw = ""
        if self._gemini:
            candidate_pool = ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-flash-lite-latest", "gemini-3.6-flash"]
            for candidate_model in candidate_pool:
                try:
                    resp = self._gemini.models.generate_content(
                        model=candidate_model,
                        contents=prompt,
                    )
                    raw = (resp.text or "").strip()
                    if raw:
                        break
                except Exception as e:
                    continue

        if not raw:
            patch_data = {
                "edge_case_title": failure_reason.split(":")[0][:50] if ":" in failure_reason else "Execution Discrepancy",
                "root_cause_analysis": failure_reason,
                "corrective_rules": [lesson_text or "Validate and coerce unexpected payload structures before processing."],
                "patch_summary": "Auto-generated defensive edge case patch.",
            }
        else:
            # Parse mutation JSON
            try:
                raw_clean = re.sub(r"^```(?:json)?\s*", "", raw)
                raw_clean = re.sub(r"\s*```$", "", clean_raw if 'clean_raw' in locals() else raw_clean)
                match = re.search(r"\{[\s\S]*\}", raw_clean)
                patch_data = json.loads(match.group(0) if match else raw_clean, strict=False)
            except Exception as e:
                print(f"  [SKILL MUTATOR] Failed to parse patch JSON: {e} — using heuristic patch")
                patch_data = {
                    "edge_case_title": "Execution Discrepancy",
                    "root_cause_analysis": failure_reason,
                    "corrective_rules": [lesson_text or "Validate and coerce unexpected payload structures before processing."],
                    "patch_summary": "Auto-generated defensive edge case patch.",
                }

        new_version = self._bump_version(current_version)
        edge_case_title = patch_data.get("edge_case_title", "Discovered Execution Edge Case")
        root_cause = patch_data.get("root_cause_analysis", "")
        rules = patch_data.get("corrective_rules", [])
        snippet = patch_data.get("example_snippet", "")
        summary = patch_data.get("summary_of_changes", f"Evolved to v{new_version}")

        # Construct markdown section for the evolution
        rules_md = "\n".join(f"- **Rule**: {r}" for r in rules)
        snippet_md = f"\n```\n{snippet}\n```" if snippet else ""
        now_date = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

        evolution_block = f"""
## 🧬 Evolution v{new_version} — {edge_case_title} ({now_date})
* **Trigger Analysis**: {root_cause}
{rules_md}{snippet_md}
"""

        # Update frontmatter version
        frontmatter["version"] = new_version
        frontmatter["updated_at"] = now_date

        fm_lines = ["---"]
        for k, v in frontmatter.items():
            fm_lines.append(f"{k}: {v}")
        fm_lines.append("---")
        new_frontmatter_text = "\n".join(fm_lines)

        updated_full_content = f"{new_frontmatter_text}\n{existing_body.strip()}\n{evolution_block}"

        # Write patched SKILL.md
        try:
            skill_file.write_text(updated_full_content, encoding="utf-8")
            print(f"  [SKILL EVOLVED] Mutated {skill_id} ({current_version} -> v{new_version}): {edge_case_title}")
        except Exception as e:
            print(f"  [SKILL MUTATOR] Failed writing updated SKILL.md: {e}")
            return None

        # Record in SQLite database
        rec_id = self._db.record_mutation(
            skill_id=skill_id,
            from_version=current_version,
            to_version=new_version,
            trigger_reason=failure_reason,
            edge_case_title=edge_case_title,
            diff_summary=summary,
            patch_json=json.dumps(patch_data),
        )

        # Trigger vector index re-synchronization
        if self._skill_manager:
            try:
                self._skill_manager.reload_skills()
            except Exception as e:
                print(f"  [SKILL MUTATOR] Skill reload failed: {e}")

        return MutationRecord(
            skill_id=skill_id,
            from_version=current_version,
            to_version=new_version,
            trigger_reason=failure_reason,
            edge_case_title=edge_case_title,
            diff_summary=summary,
            id=rec_id,
        )
