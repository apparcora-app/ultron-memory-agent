"""
================================================================================
 ULTRON COGNITIVE ARCHITECTURE — DYNAMIC GRAPH-RAG & CAUSAL KNOWLEDGE GRAPH
================================================================================
Module: graph_rag_engine.py
Pillar: Cognitive Breakthrough 2 — Dynamic Graph-RAG & Causal Entity Linking

Implements:
  1. KnowledgeGraphStore: SQLite-backed persistent knowledge graph with entities,
     directed relational triples, and causal chains.
  2. EntityRelationExtractor: LLM + regex heuristic extractor for entities,
     relationships, and causal dependency edges.
  3. CausalInferenceEngine: Traverses causal provenance chains (Event -> Cause -> Resolution).
  4. GraphRAGTraverser: Performs N-hop neighborhood expansion, path discovery,
     and formats structured sub-graph context for LLM prompt augmentation.

Author: Ultron Cybernetic Systems Architect
================================================================================
"""

from __future__ import annotations

import json
import math
import os
import re
import sqlite3
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

# Ensure UTF-8 stdout/stderr on Windows console
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import anthropic
from dotenv import load_dotenv

# Try Google GenAI SDK
try:
    from google import genai
    from google.genai import types as genai_types
    _HAS_GEMINI = True
except ImportError:
    _HAS_GEMINI = False

from config import LLMConfig
from telemetry import TelemetryEngine


# ──────────────────────────────────────────────────────────────────────────────
# DATA STRUCTURES
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class GraphEntity:
    """Represents a discrete node / entity in the Knowledge Graph."""
    id: str
    name: str
    entity_type: str  # PERSON, SYSTEM, TOOL, ORGANIZATION, METRIC, ERROR, CONCEPT, ARTIFACT
    aliases: List[str] = field(default_factory=list)
    description: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class GraphTriple:
    """Represents a directed relational edge between two entities (Head -> Relation -> Tail)."""
    id: str
    source_id: str
    relation: str  # ARCHITECTED, REQUIRES, CALLS, CAUSED_BY, RESOLVED_BY, PART_OF, MUTATED_TO, LINKED_TO
    target_id: str
    weight: float = 1.0
    confidence: float = 1.0
    is_causal: bool = False
    context_snippet: str = ""
    created_at: float = field(default_factory=time.time)


@dataclass
class CausalChain:
    """Represents a structured cause-and-effect dependency sequence."""
    id: str
    trigger_event: str
    root_cause: str
    intermediate_steps: List[str] = field(default_factory=list)
    resolution_strategy: str = ""
    outcome: str = ""
    source_tool: Optional[str] = None
    created_at: float = field(default_factory=time.time)


@dataclass
class SubGraphContext:
    """Packaged sub-graph result for LLM prompt augmentation."""
    seed_entities: List[GraphEntity]
    connected_entities: List[GraphEntity]
    triples: List[GraphTriple]
    causal_chains: List[CausalChain]
    formatted_markdown: str
    hop_depth: int
    traversal_time_s: float

    @property
    def entities(self) -> List[GraphEntity]:
        """All unique entities in the subgraph (seeds + connected)."""
        seen = set()
        res = []
        for e in self.seed_entities + self.connected_entities:
            if e.id not in seen:
                seen.add(e.id)
                res.append(e)
        return res

    def __getitem__(self, item: str):
        """Allows dictionary subscripting like res['entities'] and res['triples']."""
        if item == "entities":
            return self.entities
        if item == "triples":
            return self.triples
        if item == "causal_chains":
            return self.causal_chains
        if item == "seed_entities":
            return self.seed_entities
        if item == "connected_entities":
            return self.connected_entities
        if item == "formatted_markdown":
            return self.formatted_markdown
        raise KeyError(item)


# ──────────────────────────────────────────────────────────────────────────────
# PROMPTS
# ──────────────────────────────────────────────────────────────────────────────

_EXTRACTION_PROMPT = """You are an expert Knowledge Graph & Entity Relation Extractor for an advanced AI Agent system.
Analyze the following text (which may contain user instructions, agent reasoning, or tool outputs) and extract structured entities, directed relationships, and causal dependency links.

TEXT TO ANALYZE:
\"\"\"{text}\"\"\"

EXTRACTION INSTRUCTIONS:
1. Identify distinct entities (Person, System, Tool, Organization, Error, Metric, Concept, File).
2. Identify directed relational triples between entities: (Source Entity) --[RELATION]--> (Target Entity).
   Standard relations: ARCHITECTED, BUILT, REQUIRES_SKILL, USES_TOOL, CONFIGURED_WITH, CAUSED_BY, RESOLVED_BY, PART_OF, MUTATED_TO, PRODUCED, BELONGS_TO.
3. If an error, failure, or bug fix is mentioned, identify the causal chain (Trigger Event -> Root Cause -> Resolution Strategy -> Outcome).
4. Output STRICT JSON ONLY matching this exact schema:

```json
{{
  "entities": [
    {{
      "name": "Exact Entity Name",
      "entity_type": "PERSON | SYSTEM | TOOL | ORGANIZATION | ERROR | METRIC | CONCEPT | ARTIFACT",
      "aliases": ["Alias 1", "Alias 2"],
      "description": "Brief 1-sentence summary of this entity"
    }}
  ],
  "triples": [
    {{
      "source_name": "Source Entity Name",
      "relation": "RELATION_NAME",
      "target_name": "Target Entity Name",
      "is_causal": false,
      "confidence": 0.95,
      "context_snippet": "Brief supporting sentence from text"
    }}
  ],
  "causal_chains": [
    {{
      "trigger_event": "What triggered the error/event",
      "root_cause": "Why it happened",
      "intermediate_steps": ["Step 1", "Step 2"],
      "resolution_strategy": "How it was fixed or handled",
      "outcome": "Final result (e.g. Success, 100% Pass)"
    }}
  ]
}}
```

Respond with ONLY valid JSON inside markdown code fences."""


# ──────────────────────────────────────────────────────────────────────────────
# KNOWLEDGE GRAPH SQLITE STORE
# ──────────────────────────────────────────────────────────────────────────────

class KnowledgeGraphStore:
    """
    Persistent SQLite storage engine for entities, relational triples, and causal chains.
    Supports atomic operations, alias indexing, and multi-hop neighborhood traversals.
    """

    def __init__(self, db_path: str = "./data/knowledge_graph.sqlite3") -> None:
        self.db_path = Path(db_path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _init_db(self) -> None:
        """Initializes database schema with indexing."""
        with self._get_conn() as conn:
            # 1. Entities Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS entities (
                    id TEXT PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL COLLATE NOCASE,
                    entity_type TEXT NOT NULL,
                    aliases_json TEXT NOT NULL DEFAULT '[]',
                    description TEXT NOT NULL DEFAULT '',
                    properties_json TEXT NOT NULL DEFAULT '{}',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);")

            # 2. Triples Table (Directed Edges)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS triples (
                    id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    relation TEXT NOT NULL COLLATE NOCASE,
                    target_id TEXT NOT NULL,
                    weight REAL NOT NULL DEFAULT 1.0,
                    confidence REAL NOT NULL DEFAULT 1.0,
                    is_causal INTEGER NOT NULL DEFAULT 0,
                    context_snippet TEXT NOT NULL DEFAULT '',
                    created_at REAL NOT NULL,
                    FOREIGN KEY (source_id) REFERENCES entities(id) ON DELETE CASCADE,
                    FOREIGN KEY (target_id) REFERENCES entities(id) ON DELETE CASCADE,
                    UNIQUE(source_id, relation, target_id)
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_triples_source ON triples(source_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_triples_target ON triples(target_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_triples_relation ON triples(relation);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_triples_causal ON triples(is_causal);")

            # 3. Causal Chains Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS causal_chains (
                    id TEXT PRIMARY KEY,
                    trigger_event TEXT NOT NULL,
                    root_cause TEXT NOT NULL,
                    intermediate_steps_json TEXT NOT NULL DEFAULT '[]',
                    resolution_strategy TEXT NOT NULL DEFAULT '',
                    outcome TEXT NOT NULL DEFAULT '',
                    source_tool TEXT,
                    created_at REAL NOT NULL
                );
            """)
            conn.commit()

    # ── Entity Operations ─────────────────────────────────────────────────────

    def upsert_entity(
        self,
        name: str,
        entity_type: str = "CONCEPT",
        aliases: Optional[List[str]] = None,
        description: str = "",
        properties: Optional[Dict[str, Any]] = None,
    ) -> GraphEntity:
        """Inserts or updates an entity, merging aliases and descriptions."""
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Entity name cannot be empty")

        now = time.time()
        aliases = aliases or []
        properties = properties or {}

        with self._get_conn() as conn:
            cur = conn.cursor()
            existing = cur.execute("SELECT * FROM entities WHERE name = ?", (clean_name,)).fetchone()
            if existing:
                ent_id = existing["id"]
                # Merge aliases
                try:
                    cur_aliases = json.loads(existing["aliases_json"])
                except Exception:
                    cur_aliases = []
                merged_aliases = list(set(cur_aliases + aliases))

                # Update description if new one is richer
                cur_desc = existing["description"]
                new_desc = description if len(description) > len(cur_desc) else cur_desc

                cur.execute(
                    """
                    UPDATE entities
                    SET entity_type = ?, aliases_json = ?, description = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (entity_type or existing["entity_type"], json.dumps(merged_aliases), new_desc, now, ent_id),
                )
                conn.commit()
                return GraphEntity(
                    id=ent_id,
                    name=clean_name,
                    entity_type=entity_type or existing["entity_type"],
                    aliases=merged_aliases,
                    description=new_desc,
                    properties=properties,
                    created_at=existing["created_at"],
                    updated_at=now,
                )
            else:
                ent_id = f"ent_{uuid.uuid4().hex[:12]}"
                cur.execute(
                    """
                    INSERT INTO entities (id, name, entity_type, aliases_json, description, properties_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (ent_id, clean_name, entity_type, json.dumps(aliases), description, json.dumps(properties), now, now),
                )
                conn.commit()
                return GraphEntity(
                    id=ent_id,
                    name=clean_name,
                    entity_type=entity_type,
                    aliases=aliases,
                    description=description,
                    properties=properties,
                    created_at=now,
                    updated_at=now,
                )

    def get_entity_by_name(self, name: str) -> Optional[GraphEntity]:
        """Resolves an entity by exact name or registered alias."""
        clean_name = name.strip().lower()
        with self._get_conn() as conn:
            cur = conn.cursor()
            # 1. Exact match on name
            row = cur.execute("SELECT * FROM entities WHERE LOWER(name) = ?", (clean_name,)).fetchone()
            if row:
                return self._row_to_entity(row)

            # 2. Search aliases
            all_rows = cur.execute("SELECT * FROM entities").fetchall()
            for r in all_rows:
                try:
                    aliases = [a.lower() for a in json.loads(r["aliases_json"])]
                    if clean_name in aliases:
                        return self._row_to_entity(r)
                except Exception:
                    pass
        return None

    def get_entity_by_id(self, entity_id: str) -> Optional[GraphEntity]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM entities WHERE id = ?", (entity_id,)).fetchone()
            if row:
                return self._row_to_entity(row)
        return None

    def _row_to_entity(self, row: sqlite3.Row) -> GraphEntity:
        try:
            aliases = json.loads(row["aliases_json"])
        except Exception:
            aliases = []
        try:
            props = json.loads(row["properties_json"])
        except Exception:
            props = {}
        return GraphEntity(
            id=row["id"],
            name=row["name"],
            entity_type=row["entity_type"],
            aliases=aliases,
            description=row["description"],
            properties=props,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    # ── Triple Operations (Edges) ─────────────────────────────────────────────

    def upsert_triple(
        self,
        source_name: str,
        relation: str,
        target_name: str,
        source_type: str = "CONCEPT",
        target_type: str = "CONCEPT",
        weight: float = 1.0,
        confidence: float = 1.0,
        is_causal: bool = False,
        context_snippet: str = "",
    ) -> GraphTriple:
        """Upserts source and target entities, then creates a directed relationship edge."""
        src_ent = self.upsert_entity(source_name, entity_type=source_type)
        tgt_ent = self.upsert_entity(target_name, entity_type=target_type)

        clean_rel = relation.strip().upper().replace(" ", "_")
        now = time.time()

        with self._get_conn() as conn:
            cur = conn.cursor()
            existing = cur.execute(
                "SELECT * FROM triples WHERE source_id = ? AND relation = ? AND target_id = ?",
                (src_ent.id, clean_rel, tgt_ent.id),
            ).fetchone()

            if existing:
                t_id = existing["id"]
                cur.execute(
                    """
                    UPDATE triples
                    SET weight = ?, confidence = ?, is_causal = ?, context_snippet = ?
                    WHERE id = ?
                    """,
                    (max(existing["weight"], weight), max(existing["confidence"], confidence), int(is_causal), context_snippet or existing["context_snippet"], t_id),
                )
                conn.commit()
                return GraphTriple(
                    id=t_id,
                    source_id=src_ent.id,
                    relation=clean_rel,
                    target_id=tgt_ent.id,
                    weight=max(existing["weight"], weight),
                    confidence=max(existing["confidence"], confidence),
                    is_causal=is_causal,
                    context_snippet=context_snippet or existing["context_snippet"],
                    created_at=existing["created_at"],
                )
            else:
                t_id = f"trip_{uuid.uuid4().hex[:12]}"
                cur.execute(
                    """
                    INSERT INTO triples (id, source_id, relation, target_id, weight, confidence, is_causal, context_snippet, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (t_id, src_ent.id, clean_rel, tgt_ent.id, weight, confidence, int(is_causal), context_snippet, now),
                )
                conn.commit()
                return GraphTriple(
                    id=t_id,
                    source_id=src_ent.id,
                    relation=clean_rel,
                    target_id=tgt_ent.id,
                    weight=weight,
                    confidence=confidence,
                    is_causal=is_causal,
                    context_snippet=context_snippet,
                    created_at=now,
                )

    # ── Causal Chain Operations ───────────────────────────────────────────────

    def add_causal_chain(
        self,
        trigger_event: str,
        root_cause: str,
        intermediate_steps: Optional[List[str]] = None,
        resolution_strategy: str = "",
        outcome: str = "",
        source_tool: Optional[str] = None,
    ) -> CausalChain:
        """Stores a structured cause-and-effect reasoning chain."""
        steps = intermediate_steps or []
        chain_id = f"causal_{uuid.uuid4().hex[:12]}"
        now = time.time()

        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO causal_chains (id, trigger_event, root_cause, intermediate_steps_json, resolution_strategy, outcome, source_tool, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (chain_id, trigger_event, root_cause, json.dumps(steps), resolution_strategy, outcome, source_tool, now),
            )
            conn.commit()

        # Also link as causal triples if appropriate
        if trigger_event and root_cause:
            self.upsert_triple(
                source_name=trigger_event[:60],
                relation="CAUSED_BY",
                target_name=root_cause[:60],
                source_type="ERROR",
                target_type="CONCEPT",
                is_causal=True,
                context_snippet=f"Resolution: {resolution_strategy}",
            )
        if root_cause and resolution_strategy:
            self.upsert_triple(
                source_name=root_cause[:60],
                relation="RESOLVED_BY",
                target_name=resolution_strategy[:60],
                source_type="CONCEPT",
                target_type="TOOL" if source_tool else "CONCEPT",
                is_causal=True,
                context_snippet=f"Outcome: {outcome}",
            )

        return CausalChain(
            id=chain_id,
            trigger_event=trigger_event,
            root_cause=root_cause,
            intermediate_steps=steps,
            resolution_strategy=resolution_strategy,
            outcome=outcome,
            source_tool=source_tool,
            created_at=now,
        )

    def get_recent_causal_chains(self, limit: int = 10) -> List[CausalChain]:
        """Retrieves recent causal chains."""
        with self._get_conn() as conn:
            rows = conn.execute("SELECT * FROM causal_chains ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
            chains = []
            for r in rows:
                try:
                    steps = json.loads(r["intermediate_steps_json"])
                except Exception:
                    steps = []
                chains.append(CausalChain(
                    id=r["id"],
                    trigger_event=r["trigger_event"],
                    root_cause=r["root_cause"],
                    intermediate_steps=steps,
                    resolution_strategy=r["resolution_strategy"],
                    outcome=r["outcome"],
                    source_tool=r["source_tool"],
                    created_at=r["created_at"],
                ))
            return chains

    # ── Graph Traversal & Search ──────────────────────────────────────────────

    def get_neighbors(self, entity_id: str, direction: str = "both") -> List[Tuple[GraphTriple, GraphEntity]]:
        """
        Retrieves direct 1-hop neighbors of an entity.
        direction: 'out' (source=entity_id), 'in' (target=entity_id), or 'both'.
        """
        neighbors = []
        with self._get_conn() as conn:
            cur = conn.cursor()
            if direction in ("out", "both"):
                out_rows = cur.execute(
                    """
                    SELECT t.*, e.name as target_name, e.entity_type as target_type, e.aliases_json as target_aliases,
                           e.description as target_desc, e.properties_json as target_props, e.created_at as target_created, e.updated_at as target_updated
                    FROM triples t
                    JOIN entities e ON t.target_id = e.id
                    WHERE t.source_id = ?
                    """,
                    (entity_id,),
                ).fetchall()
                for r in out_rows:
                    triple = GraphTriple(
                        id=r["id"],
                        source_id=r["source_id"],
                        relation=r["relation"],
                        target_id=r["target_id"],
                        weight=r["weight"],
                        confidence=r["confidence"],
                        is_causal=bool(r["is_causal"]),
                        context_snippet=r["context_snippet"],
                        created_at=r["created_at"],
                    )
                    try:
                        aliases = json.loads(r["target_aliases"])
                    except Exception:
                        aliases = []
                    try:
                        props = json.loads(r["target_props"])
                    except Exception:
                        props = {}
                    ent = GraphEntity(
                        id=r["target_id"],
                        name=r["target_name"],
                        entity_type=r["target_type"],
                        aliases=aliases,
                        description=r["target_desc"],
                        properties=props,
                        created_at=r["target_created"],
                        updated_at=r["target_updated"],
                    )
                    neighbors.append((triple, ent))

            if direction in ("in", "both"):
                in_rows = cur.execute(
                    """
                    SELECT t.*, e.name as source_name, e.entity_type as source_type, e.aliases_json as source_aliases,
                           e.description as source_desc, e.properties_json as source_props, e.created_at as source_created, e.updated_at as source_updated
                    FROM triples t
                    JOIN entities e ON t.source_id = e.id
                    WHERE t.target_id = ?
                    """,
                    (entity_id,),
                ).fetchall()
                for r in in_rows:
                    triple = GraphTriple(
                        id=r["id"],
                        source_id=r["source_id"],
                        relation=r["relation"],
                        target_id=r["target_id"],
                        weight=r["weight"],
                        confidence=r["confidence"],
                        is_causal=bool(r["is_causal"]),
                        context_snippet=r["context_snippet"],
                        created_at=r["created_at"],
                    )
                    try:
                        aliases = json.loads(r["source_aliases"])
                    except Exception:
                        aliases = []
                    try:
                        props = json.loads(r["source_props"])
                    except Exception:
                        props = {}
                    ent = GraphEntity(
                        id=r["source_id"],
                        name=r["source_name"],
                        entity_type=r["source_type"],
                        aliases=aliases,
                        description=r["source_desc"],
                        properties=props,
                        created_at=r["source_created"],
                        updated_at=r["source_updated"],
                    )
                    neighbors.append((triple, ent))

        return neighbors

    def get_subgraph(self, seed_entity_ids: List[str], max_hops: int = 2, max_nodes: int = 30) -> Tuple[List[GraphEntity], List[GraphTriple]]:
        """
        Extracts an N-hop neighborhood subgraph around seed entities via Breadth-First Search.
        """
        visited_nodes: Set[str] = set()
        collected_entities: Dict[str, GraphEntity] = {}
        collected_triples: Dict[str, GraphTriple] = {}

        queue: List[Tuple[str, int]] = [(sid, 0) for sid in seed_entity_ids]

        # Ingest seed entities
        for sid in seed_entity_ids:
            ent = self.get_entity_by_id(sid)
            if ent:
                collected_entities[ent.id] = ent

        while queue and len(collected_entities) < max_nodes:
            curr_id, curr_hop = queue.pop(0)
            if curr_id in visited_nodes or curr_hop >= max_hops:
                continue

            visited_nodes.add(curr_id)
            neighbors = self.get_neighbors(curr_id, direction="both")

            for triple, neighbor_ent in neighbors:
                collected_triples[triple.id] = triple
                if neighbor_ent.id not in collected_entities:
                    collected_entities[neighbor_ent.id] = neighbor_ent
                    if curr_hop + 1 < max_hops:
                        queue.append((neighbor_ent.id, curr_hop + 1))

        return list(collected_entities.values()), list(collected_triples.values())

    def get_stats(self) -> Dict[str, int]:
        """Returns entity and edge counts."""
        with self._get_conn() as conn:
            cur = conn.cursor()
            e_count = cur.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
            t_count = cur.execute("SELECT COUNT(*) FROM triples").fetchone()[0]
            c_count = cur.execute("SELECT COUNT(*) FROM causal_chains").fetchone()[0]
            return {"total_entities": e_count, "total_triples": t_count, "total_causal_chains": c_count}


# ──────────────────────────────────────────────────────────────────────────────
# ENTITY & RELATION EXTRACTOR
# ──────────────────────────────────────────────────────────────────────────────

class EntityRelationExtractor:
    """
    LLM-powered entity and relation extractor with regex heuristic fallbacks.
    Extracts structured entities, relations, and causal links from conversation turns.
    """

    def __init__(
        self,
        claude: Optional[anthropic.Anthropic] = None,
        gemini: Any = None,
        haiku_model: str = "claude-haiku-4-5-20251001",
        gemini_model: str = "gemini-2.5-flash",
        provider: str = "anthropic",
    ) -> None:
        self.claude = claude
        self.gemini = gemini
        self.haiku_model = haiku_model
        self.gemini_model = gemini_model
        self.provider = provider

    def extract_from_text(self, text: str) -> Dict[str, Any]:
        """Extracts structured entities, triples, and causal chains from text."""
        if not text or len(text.strip()) < 10:
            return {"entities": [], "triples": [], "causal_chains": []}

        prompt = _EXTRACTION_PROMPT.format(text=text[:3000])
        raw_json = self._call_llm(prompt)

        # 1. Clean markdown code fences
        cleaned = re.sub(r"^```(?:json)?\s*", "", raw_json.strip(), flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned.strip())

        try:
            data = json.loads(cleaned)
            if isinstance(data, dict):
                return {
                    "entities": data.get("entities", []),
                    "triples": data.get("triples", []),
                    "causal_chains": data.get("causal_chains", []),
                }
        except Exception:
            pass

        # Fallback regex-based extraction
        return self._fallback_regex_extract(text)

    def _call_llm(self, prompt: str) -> str:
        if self.gemini and _HAS_GEMINI:
            candidate_pool = ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-flash-lite-latest", "gemini-3.6-flash"]
            for candidate_model in candidate_pool:
                try:
                    resp = self.gemini.models.generate_content(
                        model=candidate_model,
                        contents=prompt,
                    )
                    if resp and resp.text:
                        return resp.text.strip()
                except Exception:
                    continue

        return "{}"

    def _fallback_regex_extract(self, text: str) -> Dict[str, Any]:
        """Rule-based heuristic extractor for offline or fallback scenarios."""
        entities = []
        triples = []
        causal_chains = []

        # Known entity keywords
        known_keywords = [
            ("Hanzla Rehman", "PERSON", ["Boss", "Hanzla"]),
            ("Ultron Protocol", "SYSTEM", ["Ultron", "Agent"]),
            ("Tree-of-Thoughts Engine", "SYSTEM", ["ToT", "MCTS"]),
            ("Episodic Trajectory Bank", "SYSTEM", ["Trajectory Bank", "ExpeL"]),
            ("In-Flight Critic Gate", "SYSTEM", ["Critic Gate", "Proposer/Critic"]),
            ("Deloitte", "ORGANIZATION", ["Deloitte Consulting"]),
            ("LangGraph", "TOOL", ["StateGraph"]),
            ("CrewAI", "TOOL", ["Crew Swarm"]),
            ("Model Context Protocol", "TOOL", ["MCP"]),
            ("ChromaDB", "TOOL", ["Vector Store"]),
            ("Prometheus Telemetry", "TOOL", ["Prometheus", "Telemetry"]),
            ("FastAPI", "TOOL", ["Backend"]),
        ]

        text_lower = text.lower()
        for name, etype, aliases in known_keywords:
            if name.lower() in text_lower or any(a.lower() in text_lower for a in aliases):
                entities.append({
                    "name": name,
                    "entity_type": etype,
                    "aliases": aliases,
                    "description": f"Extracted system entity: {name}",
                })

        # Relational links
        if any(e["name"] == "Hanzla Rehman" for e in entities) and any(e["name"] == "Ultron Protocol" for e in entities):
            triples.append({
                "source_name": "Hanzla Rehman",
                "relation": "ARCHITECTED",
                "target_name": "Ultron Protocol",
                "is_causal": False,
                "confidence": 1.0,
                "context_snippet": "Hanzla Rehman architected Ultron Protocol.",
            })

        return {"entities": entities, "triples": triples, "causal_chains": causal_chains}


# ──────────────────────────────────────────────────────────────────────────────
# GRAPH-RAG TRAVERSER & CAUSAL REASONING CORE
# ──────────────────────────────────────────────────────────────────────────────

class GraphRAGEngine:
    """
    Unified Dynamic Graph-RAG and Causal Knowledge Graph Coordinator.
    Performs real-time entity linking, multi-hop sub-graph assembly,
    and causal provenance querying for agent prompt augmentation.
    """

    def __init__(
        self,
        db_path: str = "./data/knowledge_graph.sqlite3",
        claude: Optional[anthropic.Anthropic] = None,
        gemini: Any = None,
        haiku_model: str = "claude-haiku-4-5-20251001",
        gemini_model: str = "gemini-2.5-flash",
        provider: str = "anthropic",
        telemetry: Optional[TelemetryEngine] = None,
    ) -> None:
        self.store = KnowledgeGraphStore(db_path=db_path)
        self.extractor = EntityRelationExtractor(
            claude=claude,
            gemini=gemini,
            haiku_model=haiku_model,
            gemini_model=gemini_model,
            provider=provider,
        )
        self.telemetry = telemetry
        self._seed_default_foundational_graph()

    def _seed_default_foundational_graph(self) -> None:
        """Seeds foundational entities and relationships if graph is empty."""
        stats = self.store.get_stats()
        if stats["total_entities"] == 0:
            # Seed Creator & Systems
            self.store.upsert_entity("Hanzla Rehman", "PERSON", aliases=["Boss", "Hanzla", "Architect"], description="Lead Agentic AI Engineer & Systems Architect")
            self.store.upsert_entity("Ultron Protocol", "SYSTEM", aliases=["Ultron", "Cybernetic Mainframe"], description="Production-grade autonomous multi-agent AI system")
            self.store.upsert_entity("LangGraph", "TOOL", aliases=["StateGraph"], description="Stateful multi-agent DAG orchestration framework")
            self.store.upsert_entity("CrewAI", "TOOL", aliases=["Crew Swarm"], description="Collaborative multi-persona agent swarm framework")
            self.store.upsert_entity("Model Context Protocol", "TOOL", aliases=["MCP"], description="Standardized protocol connecting external tools to LLMs")
            self.store.upsert_entity("Tree-of-Thoughts Engine", "SYSTEM", aliases=["ToT", "MCTS"], description="Monte Carlo Tree Search multi-branch reasoning engine")
            self.store.upsert_entity("In-Flight Critic Gate", "SYSTEM", aliases=["Critic Gate"], description="Pre-response verification and hallucination filter")
            self.store.upsert_entity("Episodic Trajectory Bank", "SYSTEM", aliases=["Trajectory Bank", "ExpeL"], description="ChromaDB few-shot trajectory replay store")
            self.store.upsert_entity("ChromaDB", "TOOL", description="Dense semantic vector database")
            self.store.upsert_entity("Prometheus Telemetry", "TOOL", aliases=["Telemetry"], description="Real-time observability and audit logging engine")

            # Seed Foundational Triples
            self.store.upsert_triple("Hanzla Rehman", "ARCHITECTED", "Ultron Protocol", "PERSON", "SYSTEM")
            self.store.upsert_triple("Ultron Protocol", "USES_FRAMEWORK", "LangGraph", "SYSTEM", "TOOL")
            self.store.upsert_triple("Ultron Protocol", "USES_FRAMEWORK", "CrewAI", "SYSTEM", "TOOL")
            self.store.upsert_triple("Ultron Protocol", "INTEGRATES_TOOL", "Model Context Protocol", "SYSTEM", "TOOL")
            self.store.upsert_triple("Ultron Protocol", "HAS_SUBSYSTEM", "Tree-of-Thoughts Engine", "SYSTEM", "SYSTEM")
            self.store.upsert_triple("Ultron Protocol", "HAS_SUBSYSTEM", "In-Flight Critic Gate", "SYSTEM", "SYSTEM")
            self.store.upsert_triple("Ultron Protocol", "HAS_SUBSYSTEM", "Episodic Trajectory Bank", "SYSTEM", "SYSTEM")
            self.store.upsert_triple("Episodic Trajectory Bank", "STORES_IN", "ChromaDB", "SYSTEM", "TOOL")
            self.store.upsert_triple("Ultron Protocol", "MONITORED_BY", "Prometheus Telemetry", "SYSTEM", "TOOL")

            # Seed Foundational Causal Provenance Chains
            self.store.add_causal_chain(
                trigger_event="Swarm tasks missing from Prometheus metrics",
                root_cause="Missing telemetry execution hooks in subagent handlers",
                intermediate_steps=["Traced telemetry.db calls", "Discovered uninstrumented LangGraph nodes"],
                resolution_strategy="Re-instrumented per-run and per-subtask telemetry hooks",
                outcome="Verified live: swarm runs counter 0 -> 1, subtasks 0 -> 5",
                source_tool="telemetry",
            )
            self.store.add_causal_chain(
                trigger_event="Tool execution exceptions softly paraphrased as success",
                root_cause="LLM Paraphrasing unchecked return codes",
                intermediate_steps=["Inspected raw tool dicts", "Found unhandled exceptions formatted as text"],
                resolution_strategy="Enforced deterministic classification gates in isolated AST sandbox",
                outcome="Eliminated false-success tool hallucinations",
                source_tool="sandbox",
            )

    def insert_triple(self, source_name: str, relation: str, target_name: str, **kwargs) -> GraphTriple:
        """Alias for store.upsert_triple."""
        return self.store.upsert_triple(source_name=source_name, relation=relation, target_name=target_name, **kwargs)

    def upsert_triple(self, source_name: str, relation: str, target_name: str, **kwargs) -> GraphTriple:
        """Upserts a relational edge between two entities."""
        return self.store.upsert_triple(source_name=source_name, relation=relation, target_name=target_name, **kwargs)

    def insert_entity(self, name: str, entity_type: str = "CONCEPT", **kwargs) -> GraphEntity:
        """Alias for store.upsert_entity."""
        return self.store.upsert_entity(name=name, entity_type=entity_type, **kwargs)

    def upsert_entity(self, name: str, entity_type: str = "CONCEPT", **kwargs) -> GraphEntity:
        """Upserts an entity with properties and aliases."""
        return self.store.upsert_entity(name=name, entity_type=entity_type, **kwargs)

    def hybrid_graph_rag_query(self, query: str, max_hops: int = 2, max_nodes: int = 20) -> SubGraphContext:
        """Executes hybrid Graph-RAG subgraph extraction and semantic expansion."""
        return self.query_subgraph(query=query, max_hops=max_hops, max_nodes=max_nodes)

    def ingest_text(self, text: str, source_context: str = "conversation") -> Dict[str, int]:
        """
        Extracts entities, triples, and causal chains from text and persists them into the graph.
        """
        extracted = self.extractor.extract_from_text(text)
        entities_added = 0
        triples_added = 0
        causal_added = 0

        # 1. Upsert Entities
        name_to_entity = {}
        for ent_dict in extracted.get("entities", []):
            name = ent_dict.get("name")
            if name:
                ent = self.store.upsert_entity(
                    name=name,
                    entity_type=ent_dict.get("entity_type", "CONCEPT"),
                    aliases=ent_dict.get("aliases", []),
                    description=ent_dict.get("description", ""),
                )
                name_to_entity[name.lower()] = ent
                entities_added += 1

        # 2. Upsert Triples
        for trip_dict in extracted.get("triples", []):
            src_name = trip_dict.get("source_name")
            rel = trip_dict.get("relation")
            tgt_name = trip_dict.get("target_name")
            if src_name and rel and tgt_name:
                self.store.upsert_triple(
                    source_name=src_name,
                    relation=rel,
                    target_name=tgt_name,
                    is_causal=trip_dict.get("is_causal", False),
                    confidence=trip_dict.get("confidence", 1.0),
                    context_snippet=trip_dict.get("context_snippet", ""),
                )
                triples_added += 1

        # 3. Add Causal Chains
        for chain_dict in extracted.get("causal_chains", []):
            trigger = chain_dict.get("trigger_event")
            cause = chain_dict.get("root_cause")
            if trigger and cause:
                self.store.add_causal_chain(
                    trigger_event=trigger,
                    root_cause=cause,
                    intermediate_steps=chain_dict.get("intermediate_steps", []),
                    resolution_strategy=chain_dict.get("resolution_strategy", ""),
                    outcome=chain_dict.get("outcome", ""),
                )
                causal_added += 1

        return {"entities_added": entities_added, "triples_added": triples_added, "causal_added": causal_added}

    def query_subgraph(self, query: str, max_hops: int = 2, max_nodes: int = 20) -> SubGraphContext:
        """
        Given a user query:
          1. Resolves seed entities mentioned in query (with alias expansion).
          2. Traverses the Knowledge Graph up to `max_hops`.
          3. Retrieves relevant causal provenance chains.
          4. Returns structured markdown for LLM context augmentation.
        """
        t0 = time.time()
        words = query.lower()

        # 1. Identify seed entities
        seed_entities: List[GraphEntity] = []
        with self.store._get_conn() as conn:
            all_entities = conn.execute("SELECT * FROM entities").fetchall()
            for r in all_entities:
                name_low = r["name"].lower()
                matched = False
                if name_low in words:
                    matched = True
                else:
                    try:
                        aliases = [a.lower() for a in json.loads(r["aliases_json"])]
                        if any(a in words for a in aliases):
                            matched = True
                    except Exception:
                        pass
                if matched:
                    seed_entities.append(self.store._row_to_entity(r))

        # 2. Extract N-hop Subgraph
        seed_ids = [e.id for e in seed_entities]
        connected_entities, triples = self.store.get_subgraph(seed_ids, max_hops=max_hops, max_nodes=max_nodes)

        # 3. Retrieve relevant causal chains
        relevant_causal: List[CausalChain] = []
        all_causal = self.store.get_recent_causal_chains(limit=5)
        for chain in all_causal:
            # If any seed entity or keyword matches causal event
            chain_text = f"{chain.trigger_event} {chain.root_cause} {chain.resolution_strategy}".lower()
            if any(e.name.lower() in chain_text for e in seed_entities) or any(w in chain_text for w in query.lower().split() if len(w) > 4):
                relevant_causal.append(chain)

        # 4. Format Structured Markdown for Prompt Context
        markdown_lines = []
        if seed_entities or triples or relevant_causal:
            markdown_lines.append("### 🕸️ KNOWLEDGE GRAPH CONTEXT & CAUSAL PROVENANCE (Graph-RAG)")

            # Entities
            if seed_entities:
                markdown_lines.append("\n**Identified Key Entities:**")
                for e in seed_entities:
                    desc_str = f" — {e.description}" if e.description else ""
                    markdown_lines.append(f"- **{e.name}** (`{e.entity_type}`){desc_str}")

            # Triples (Relations)
            if triples:
                markdown_lines.append("\n**Graph Relationships & Dependencies:**")
                id_to_name = {e.id: e.name for e in connected_entities}
                for t in triples[:15]:
                    src = id_to_name.get(t.source_id, t.source_id)
                    tgt = id_to_name.get(t.target_id, t.target_id)
                    causal_tag = " [CAUSAL LINK]" if t.is_causal else ""
                    snippet = f" (Context: {t.context_snippet})" if t.context_snippet else ""
                    markdown_lines.append(f"- `({src})` --**[{t.relation}]**--> `({tgt})`{causal_tag}{snippet}")

            # Causal Provenance
            if relevant_causal:
                markdown_lines.append("\n**Causal Provenance & Battle-Tested Resolutions:**")
                for c in relevant_causal[:3]:
                    markdown_lines.append(f"- **Trigger:** {c.trigger_event}")
                    markdown_lines.append(f"  • *Root Cause:* {c.root_cause}")
                    markdown_lines.append(f"  • *Resolution:* {c.resolution_strategy} (Outcome: {c.outcome})")

        formatted_md = "\n".join(markdown_lines)
        duration = time.time() - t0

        if self.telemetry and (seed_entities or triples):
            self.telemetry.log_event(
                user_id="graph_rag",
                event_type="GRAPH_RAG_SUBGRAPH_QUERY",
                module_id="graph_rag_engine",
                details={
                    "seed_count": len(seed_entities),
                    "triple_count": len(triples),
                    "causal_count": len(relevant_causal),
                    "duration_s": duration,
                },
            )

        return SubGraphContext(
            seed_entities=seed_entities,
            connected_entities=connected_entities,
            triples=triples,
            causal_chains=relevant_causal,
            formatted_markdown=formatted_md,
            hop_depth=max_hops,
            traversal_time_s=duration,
        )
