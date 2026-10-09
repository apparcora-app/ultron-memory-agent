"""
skill_manager.py â€” ClawHub / OpenClaw Compatible Skill Engine for the Ultron Protocol.

Discovers, parses, and injects modular skills from ./skills/*/SKILL.md.
Provides Reciprocal Rank Fusion (RRF) Dense Semantic Vector Search (ChromaDB) + Keyword Intent Scoring.
Allows 1-click skill installation, deletion, auto-syncing, and context matching.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from skill_evolution import SkillEvolutionDB

SKILLS_DIR = Path(__file__).parent if Path(__file__).parent.name == "skills" else Path(__file__).parent / "skills"
SKILLS_DIR.mkdir(exist_ok=True)


@dataclass
class UltronSkill:
    id: str
    name: str
    description: str
    category: str = "General"
    icon: str = "âš¡"
    tags: list[str] = field(default_factory=list)
    instructions: str = ""
    enabled: bool = True
    path: str = ""
    version: str = "1.0"
    reliability: float = 1.0
    mutations: int = 0
    always_on: bool = False


class SkillManager:
    """
    Manages discoverable, ClawHub-compatible skills for Ultron.
    Implements Reciprocal Rank Fusion (RRF) Dense Semantic Vector Indexing (ChromaDB) and Sparse Intent Scoring.
    """

    def __init__(
        self,
        skills_dir: Path | str = SKILLS_DIR,
        chroma_path: str = "./data/chroma",
        enable_vector_search: bool = True,
    ) -> None:
        self.skills_dir = Path(skills_dir)
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_path = Path(chroma_path)
        self.chroma_path.mkdir(parents=True, exist_ok=True)
        self.enable_vector_search = enable_vector_search

        self._skills: dict[str, UltronSkill] = {}
        self._vector_collection = None
        self._synced_hashes: dict[str, str] = {}
        self.evolution_db = SkillEvolutionDB(self.chroma_path.parent / "skill_evolution.db")

        self.reload_skills()
        if self.enable_vector_search:
            self._init_vector_index()
            self._sync_vector_index()

    # â”€â”€ 1. Vector Store Initialization & Synchronization â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _init_vector_index(self) -> None:
        """Initializes the local persistent ChromaDB collection for semantic skill search."""
        try:
            import os
            import chromadb
            client = chromadb.PersistentClient(path=str(self.chroma_path))
            self._vector_collection = client.get_or_create_collection(
                name="ultron_skills_index",
                metadata={"hnsw:space": "cosine"},
            )
            # Pre-populate hash cache from ChromaDB metadata to avoid redundant re-embedding
            existing = self._vector_collection.get(include=["metadatas"])
            if existing and existing.get("ids") and existing.get("metadatas"):
                for sid, meta in zip(existing["ids"], existing["metadatas"]):
                    if meta and isinstance(meta, dict) and "hash" in meta:
                        self._synced_hashes[sid] = meta["hash"]
        except Exception as e:
            print(f"  [SKILL VECTOR WARNING] Could not initialize ChromaDB vector index: {e}. Falling back to keyword search.")
            self._vector_collection = None

    def _compute_skill_doc(self, skill: UltronSkill) -> tuple[str, str]:
        """Constructs a dense representation for semantic indexing and returns (doc_text, sha256_hash)."""
        tags_str = ", ".join(skill.tags) if skill.tags else "general"
        doc_text = (
            f"Skill: {skill.name}\n"
            f"Category: {skill.category}\n"
            f"Description: {skill.description}\n"
            f"Tags: {tags_str}\n"
            f"Execution Directives:\n{skill.instructions[:2000]}"
        )
        doc_hash = hashlib.sha256(doc_text.encode("utf-8")).hexdigest()
        return doc_text, doc_hash

    def _sync_vector_index(self, force: bool = False) -> None:
        """
        Synchronizes all loaded skills with the ChromaDB vector collection.
        Uses hash caching to only embed new or modified skills.
        """
        if not self._vector_collection:
            return

        try:
            ids_to_upsert: list[str] = []
            docs_to_upsert: list[str] = []
            metas_to_upsert: list[dict[str, Any]] = []

            for skill in self._skills.values():
                if not skill.enabled:
                    continue
                doc_text, doc_hash = self._compute_skill_doc(skill)
                if force or self._synced_hashes.get(skill.id) != doc_hash:
                    ids_to_upsert.append(skill.id)
                    docs_to_upsert.append(doc_text)
                    metas_to_upsert.append({
                        "id": skill.id,
                        "name": skill.name,
                        "category": skill.category,
                        "hash": doc_hash,
                    })
                    self._synced_hashes[skill.id] = doc_hash

            if ids_to_upsert:
                self._vector_collection.upsert(
                    ids=ids_to_upsert,
                    documents=docs_to_upsert,
                    metadatas=metas_to_upsert,
                )

            # Prune removed skills from vector collection
            try:
                all_indexed = self._vector_collection.get()
                indexed_ids = set(all_indexed.get("ids", []))
                active_ids = set(self._skills.keys())
                orphaned_ids = list(indexed_ids - active_ids)
                if orphaned_ids:
                    self._vector_collection.delete(ids=orphaned_ids)
                    for oid in orphaned_ids:
                        self._synced_hashes.pop(oid, None)
            except Exception:
                pass

        except Exception as e:
            print(f"  [SKILL VECTOR SYNC ERROR] Failed to sync skill vector index: {e}")

    # â”€â”€ 2. Skill Discovery & Parsing â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def reload_skills(self) -> dict[str, UltronSkill]:
        """Scans the skills directory and loads all SKILL.md files."""
        self._skills.clear()

        for skill_folder in self.skills_dir.iterdir():
            if skill_folder.is_dir():
                skill_file = skill_folder / "SKILL.md"
                if skill_file.exists():
                    try:
                        skill = self._parse_skill_file(skill_folder.name, skill_file)
                        self._skills[skill.id] = skill
                    except Exception as e:
                        print(f"[Ultron Skill Error] Failed to load {skill_file}: {e}")

        if self._vector_collection:
            self._sync_vector_index()

        return self._skills

    def get_all_skills(self) -> list[dict[str, Any]]:
        """Returns structured metadata for all installed skills."""
        self.reload_skills()
        return [
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "category": s.category,
                "icon": s.icon,
                "tags": s.tags,
                "instructions": s.instructions,
                "enabled": s.enabled,
            }
            for s in self._skills.values()
        ]

    def install_skill(
        self,
        skill_id: str,
        name: str,
        description: str,
        instructions: str,
        category: str = "Custom",
        icon: str = "âš¡",
        tags: list[str] | None = None,
    ) -> UltronSkill:
        """Installs or updates a skill in ClawHub SKILL.md format and synchronizes vector index."""
        clean_id = re.sub(r"[^a-zA-Z0-9_-]", "_", skill_id.lower().strip())
        skill_folder = self.skills_dir / clean_id
        skill_folder.mkdir(parents=True, exist_ok=True)

        tags_str = ", ".join(tags or ["custom"])

        md_content = f"""---
name: {name}
description: {description}
category: {category}
icon: {icon}
tags: [{tags_str}]
---

# {name}

## Description
{description}

## Execution Directives & Knowledge
{instructions}
"""
        skill_file = skill_folder / "SKILL.md"
        with open(skill_file, "w", encoding="utf-8") as f:
            f.write(md_content)

        parsed_skill = self._parse_skill_file(clean_id, skill_file)
        self._skills[clean_id] = parsed_skill
        self._sync_vector_index()
        return parsed_skill

    def delete_skill(self, skill_id: str) -> bool:
        """Deletes a skill directory and removes it from the vector index and evolution database."""
        clean_id = re.sub(r"[^a-zA-Z0-9_-]", "_", skill_id.lower().strip())
        skill_folder = self.skills_dir / clean_id
        if skill_folder.exists() and skill_folder.is_dir():
            import shutil
            shutil.rmtree(skill_folder)
            self._skills.pop(clean_id, None)
            if self._vector_collection:
                try:
                    self._vector_collection.delete(ids=[clean_id])
                except Exception:
                    pass
            self._synced_hashes.pop(clean_id, None)
            if hasattr(self, "evolution_db") and self.evolution_db:
                self.evolution_db.delete_skill_metadata(clean_id)
            return True
        elif hasattr(self, "evolution_db") and self.evolution_db:
            self.evolution_db.delete_skill_metadata(clean_id)
        return False

    # â”€â”€ 3. Reciprocal Rank Fusion (RRF) Semantic Vector + Keyword Matching â”€â”€â”€

    def get_matched_skills(self, query: str, active_module: str = "", limit: int = 3) -> list[UltronSkill]:
        """
        Finds skills matching the user's query using Reciprocal Rank Fusion (RRF):
        â€¢ Dense Semantic Vector Search via ChromaDB embeddings (evaluated across top candidate results)
        â€¢ Sparse Keyword / Tag / Intent Heuristic Matcher

        Skills marked always_on: true in their frontmatter are ALWAYS prepended to results
        regardless of query relevance, and do not count against the contextual limit.
        """
        # â”€â”€ Always-On Skills (injected into every turn unconditionally) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        always_on_skills = [s for s in self._skills.values() if s.always_on and s.enabled]

        if not self._skills:
            return always_on_skills[:limit]

        query_lower = query.lower().strip()
        if not query_lower:
            base = list(self._skills.values())[:limit]
            # Merge: always-on first, then contextual (deduplicated)
            seen = {s.id for s in always_on_skills}
            merged = list(always_on_skills) + [s for s in base if s.id not in seen]
            return merged[:limit + len(always_on_skills)]

        rrf_scores: dict[str, float] = {sid: 0.0 for sid in self._skills.keys()}
        K_RRF = 20.0

        # â”€â”€ Step A: Dense Semantic Vector Ranking â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        if self._vector_collection:
            try:
                n_query = min(max(limit * 10, 40), len(self._skills))
                query_res = self._vector_collection.query(
                    query_texts=[query],
                    n_results=n_query,
                )
                if query_res and query_res.get("ids") and query_res["ids"][0]:
                    retrieved_ids = query_res["ids"][0]
                    distances = query_res.get("distances", [[]])[0]
                    for rank_idx, (sid, dist) in enumerate(zip(retrieved_ids, distances)):
                        # Strict semantic relevance boundary: distance > 0.82 is semantic noise
                        if dist <= 0.82:
                            relevance = max(0.0, 1.0 - dist)
                            rrf_scores[sid] += (relevance * 2.0) / (5.0 + rank_idx)
            except Exception as e:
                print(f"  [SKILL VECTOR QUERY WARNING] {e}")

        # â”€â”€ Step B: Sparse Keyword & Tag Intent Ranking â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        keyword_scores: dict[str, float] = {}
        intent_map = {
            "tax_professional": ["tax", "taxes", "irs", "1099", "w-2", "w2", "s-corp", "scorp", "write-off", "writeoff", "deduction", "section 179", "estimated tax", "safe harbor", "audit"],
            "financial_market_data": ["stock", "stocks", "ticker", "shares", "crypto", "bitcoin", "btc", "eth", "ethereum", "solana", "polygon", "market cap", "ohlcv", "dividend", "split", "options chain"],
            "accounting_advisory": ["accounting", "bookkeeping", "gaap", "ifrs", "asc 606", "balance sheet", "journal entry", "reconciliation", "trial balance", "quickbooks", "xero"],
            "accounting_audit": ["audit", "invoice", "forensic", "receipt", "ledger", "variance", "double-entry"],
            "financial_valuation": ["valuation", "dcf", "ebitda", "cash flow", "financial model", "npv", "irr", "wacc"],
            "agent_browser": ["browser", "agent-browser", "headless", "navigate", "dom", "click @", "snapshot", "web page", "scrape", "fill form"],
            "web_automation": ["web automation", "puppeteer", "playwright", "selenium", "auto submit", "monitor site", "cron"],
            "gog_google_workspace": ["gmail", "email", "google drive", "google sheets", "google calendar", "google docs", "contacts", "gog"],
            "mission_control": ["kanban", "task", "tasks", "mission control", "in progress", "backlog", "subtask", "dod", "epic"],
            "take_the_wheel": ["take the wheel", "guide me", "ask me the questions", "lead the way", "lead this project", "prends le volant"],
            "resume_optimizer": ["resume", "cv", "job", "cover letter", "ats", "interview", "salary", "career"],
            "resume_ats_optimizer": ["ats", "applicant tracking", "ats score", "optimize resume", "keyword optimization", "not getting interviews", "resume not working", "ats compatibility", "ats screening", "match score", "ats friendly", "ats-friendly", "job description", "ats check", "ats audit", "parser"],
            "b2b_cold_outreach": ["cold email", "outreach", "b2b", "proposal", "sales", "client pitch", "retainer"],
            "ai_automation_workflows": ["ai automation", "pipeline", "batch processing", "infsh", "inference.sh", "multi-model", "flux", "imagen"],
            "excel_data_analyst": ["excel", "xlsx", "spreadsheet", "csv", "vlookup", "pivot", "formulas", "data clean"],
            "seo_audit": ["seo", "serp", "ranking", "rankings", "search console", "gsc", "indexing", "crawl", "canonical", "core web vitals", "sitemap", "backlinks", "cannibalization", "keywords"],
        }

        for sid, skill in self._skills.items():
            if not skill.enabled:
                continue
            k_raw = 0.0
            # Direct ID or name match
            if skill.id in query_lower or skill.name.lower() in query_lower:
                k_raw += 6.0
            # Tags match
            for tag in skill.tags:
                if tag.lower() in query_lower:
                    k_raw += 4.0
            # Intent map match
            for kw in intent_map.get(sid, []):
                if kw in query_lower:
                    k_raw += 3.0
            # Module context affinity
            if active_module == "ledger_protocol" and skill.category.lower() in ["accounting", "tax", "finance"]:
                k_raw += 2.0
            elif active_module == "financial_war_room" and skill.category.lower() in ["finance", "valuation", "tax"]:
                k_raw += 2.0
            elif active_module == "career_acquisition" and skill.category.lower() in ["career", "resume"]:
                k_raw += 2.0
            elif active_module == "client_infiltration" and skill.category.lower() in ["sales", "outreach", "b2b"]:
                k_raw += 2.0

            if k_raw > 0:
                keyword_scores[sid] = k_raw

        # Sort keyword candidates by raw score and apply RRF
        sorted_keywords = sorted(keyword_scores.items(), key=lambda x: x[1], reverse=True)
        for rank_idx, (sid, k_raw) in enumerate(sorted_keywords[:30]):
            rrf_scores[sid] += (0.15 / (K_RRF + (rank_idx + 1))) * (1.0 + min(k_raw / 10.0, 1.0))

        # â”€â”€ Step C: Final Sorting & Relative Confidence Filtering â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        sorted_skills = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        if not sorted_skills or sorted_skills[0][1] <= 0.0:
            contextual = []
        else:
            top_score = sorted_skills[0][1]
            contextual = [self._skills[sorted_skills[0][0]]]
            for sid, score in sorted_skills[1:limit]:
                if score >= (top_score * 0.70) and score > 0.02:
                    contextual.append(self._skills[sid])

        # â”€â”€ Step D: Merge always-on + contextual (deduplicated) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        always_on_ids = {s.id for s in always_on_skills}
        deduped_contextual = [s for s in contextual if s.id not in always_on_ids]
        return always_on_skills + deduped_contextual

    def get_skill_context(self, query: str, active_module: str = "") -> str:
        """
        Finds skills matching the user's query or active module and formats
        them as executable directives for the system prompt.
        """
        matched_skills = self.get_matched_skills(query, active_module=active_module, limit=3)
        sections = []
        for s in matched_skills:
            badge = f"[v{s.version}" + (f" | ðŸ§¬ {s.mutations} Evolutions" if s.mutations > 0 else "") + "]"
            sections.append(f"### Skill Protocol: {s.name} {badge} ({s.category})\n{s.instructions}")

        return "\n\n".join(sections)

    def get_skill_stats(self, skill_id: str) -> dict[str, Any]:
        """Returns empirical reliability and mutation metrics for a skill."""
        if hasattr(self, "evolution_db") and self.evolution_db:
            return self.evolution_db.get_skill_stats(skill_id)
        return {"version": "1.0", "success_count": 0, "failure_count": 0, "reliability": 1.0, "mutations": 0}

    def list_recent_mutations(self, limit: int = 10) -> list[dict[str, Any]]:
        """Returns the recent autonomous skill mutation history."""
        if hasattr(self, "evolution_db") and self.evolution_db:
            return self.evolution_db.list_recent_mutations(limit)
        return []

    # â”€â”€ 4. Skill File Parser â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _parse_skill_file(self, skill_id: str, path: Path) -> UltronSkill:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        name = skill_id.replace("_", " ").title()
        description = "Ultron specialized capability module."
        category = "General"
        icon = "âš¡"
        tags = []
        version = "1.0"
        always_on = False

        # Parse YAML frontmatter if present
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter = parts[1]
                body = parts[2].strip()

                for line in frontmatter.splitlines():
                    line = line.strip()
                    if line.startswith("name:"):
                        name = line.replace("name:", "").strip()
                    elif line.startswith("version:"):
                        version = line.replace("version:", "").strip().strip("'\"")
                    elif line.startswith("description:"):
                        description = line.replace("description:", "").strip()
                    elif line.startswith("category:"):
                        category = line.replace("category:", "").strip()
                    elif line.startswith("icon:"):
                        icon = line.replace("icon:", "").strip()
                    elif line.startswith("tags:"):
                        raw_tags = line.replace("tags:", "").strip(" []")
                        tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
                    elif line.startswith("always_on:"):
                        always_on = line.replace("always_on:", "").strip().lower() == "true"

                stats = self.evolution_db.get_skill_stats(skill_id) if hasattr(self, "evolution_db") and self.evolution_db else {}
                return UltronSkill(
                    id=skill_id,
                    name=name,
                    description=description,
                    category=category,
                    icon=icon,
                    tags=tags,
                    instructions=body,
                    path=str(path),
                    version=version or stats.get("version", "1.0"),
                    reliability=stats.get("reliability", 1.0),
                    mutations=stats.get("mutations", 0),
                    always_on=always_on,
                )

        stats = self.evolution_db.get_skill_stats(skill_id) if hasattr(self, "evolution_db") and self.evolution_db else {}
        return UltronSkill(
            id=skill_id,
            name=name,
            description=description,
            category=category,
            icon=icon,
            tags=tags,
            instructions=content,
            path=str(path),
            version=version or stats.get("version", "1.0"),
            reliability=stats.get("reliability", 1.0),
            mutations=stats.get("mutations", 0),
            always_on=always_on,
        )

