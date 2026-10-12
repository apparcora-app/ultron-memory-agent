"""
config.py — Centralised configuration loader.

Reads environment variables (via .env) and builds every config dict that
Mem0 and the Anthropic chat client need. Nothing here depends on Mem0 or
Anthropic directly, so the module stays easy to unit-test in isolation.

LLM stack
─────────
  Chat completions : Anthropic Claude  (CHAT_MODEL)
  Mem0 internal    : Anthropic Claude  (MEMORY_MODEL)
  Embeddings       : Local sentence-transformers via HuggingFace (FREE, no API key)
                     Model: BAAI/bge-small-en-v1.5  →  384-dim vectors
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Silence ChromaDB internal posthog telemetry mismatch
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"
try:
    import chromadb.telemetry.product.posthog as _chroma_ph
    _chroma_ph.Posthog.capture = lambda *args, **kwargs: None
except Exception:
    pass


# ── helpers ──────────────────────────────────────────────────────────────────

def _require(key: str) -> str:
    """Return env var value or raise a clear error at startup."""
    value = os.getenv(key)
    if not value:
        raise OSError(
            f"Missing required environment variable: {key}\n"
            f"Copy .env.example → .env and fill in the value."
        )
    return value


def _get(key: str, default: str) -> str:
    return os.getenv(key, default)


def _detect_freellmapi_base_url() -> str:
    env_val = os.getenv("FREELLMAPI_BASE_URL")
    if env_val:
        return env_val
    try:
        appdata = os.getenv("APPDATA")
        if appdata:
            cfg_path = Path(appdata) / "FreeLLMAPI" / "config.json"
            if cfg_path.exists():
                import json
                with open(cfg_path, encoding="utf-8") as f:
                    cfg = json.load(f)
                    port = cfg.get("port", 31415)
                    return f"http://localhost:{port}/v1"
    except Exception:
        pass
    return "http://localhost:31415/v1"


def _detect_freellmapi_api_key() -> str:
    env_val = os.getenv("FREELLMAPI_API_KEY")
    if env_val:
        return env_val
    try:
        appdata = os.getenv("APPDATA")
        if appdata:
            db_path = Path(appdata) / "FreeLLMAPI" / "freeapi.db"
            if db_path.exists():
                import sqlite3
                conn = sqlite3.connect(str(db_path))
                c = conn.cursor()
                c.execute("SELECT value FROM settings WHERE key='unified_api_key'")
                row = c.fetchone()
                conn.close()
                if row and row[0]:
                    return row[0]
    except Exception:
        pass
    return "sk-freellmapi-local"


# ── dataclasses ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class VectorStoreConfig:
    """
    Vector store configuration.

    Defaults to embedded Qdrant which runs 100% locally in-process with no Docker
    or background services needed. Data is persisted to ./data/qdrant.
    """
    provider: str = field(default_factory=lambda: _get("VECTOR_STORE_PROVIDER", "qdrant"))
    path: str = field(default_factory=lambda: _get("VECTOR_STORE_PATH", "./data/qdrant"))
    collection_name: str = field(
        default_factory=lambda: _get("COLLECTION_NAME", "mem0_agent_claude")
    )

    def as_mem0_dict(self) -> dict:
        """Return the vector_store block expected by Mem0's Memory config."""
        if self.provider == "qdrant":
            host = _get("QDRANT_HOST", "")
            port = _get("QDRANT_PORT", "")
            if host and port:
                return {
                    "provider": "qdrant",
                    "config": {
                        "host": host,
                        "port": int(port),
                        "collection_name": self.collection_name,
                        "embedding_model_dims": 384,
                    },
                }
            return {
                "provider": "qdrant",
                "config": {
                    "path": self.path or "./data/qdrant",
                    "collection_name": self.collection_name,
                    "embedding_model_dims": 384,
                    "on_disk": True,
                },
            }

        return {
            "provider": "chroma",
            "config": {
                "collection_name": self.collection_name,
                "path": self.path,
            },
        }


# Backwards compatibility alias
QdrantConfig = VectorStoreConfig


@dataclass(frozen=True)
class LLMConfig:
    provider: str = field(default_factory=lambda: _get("LLM_PROVIDER", "gemini").lower())
    anthropic_api_key: str = field(default_factory=lambda: _get("ANTHROPIC_API_KEY", ""))
    gemini_api_key: str = field(default_factory=lambda: _get("GEMINI_API_KEY", ""))
    openrouter_api_key: str = field(default_factory=lambda: _get("OPENROUTER_API_KEY", ""))
    freellmapi_base_url: str = field(default_factory=_detect_freellmapi_base_url)
    freellmapi_api_key: str = field(default_factory=_detect_freellmapi_api_key)
    freellmapi_enabled: bool = field(default_factory=lambda: _get("FREELLMAPI_ENABLED", "true").lower() in ("true", "1", "yes"))
    freellmapi_model: str = field(default_factory=lambda: _get("FREELLMAPI_MODEL", "gpt-oss-120b"))
    providers: list[str] = field(
        default_factory=lambda: [
            p for p in ["freellmapi", "gemini", "openrouter"]
            if (p == "freellmapi" and _get("FREELLMAPI_ENABLED", "true").lower() in ("true", "1", "yes"))
            or (p == "gemini" and _get("GEMINI_API_KEY", ""))
            or (p == "openrouter" and _get("OPENROUTER_API_KEY", ""))
        ] or ["freellmapi"]
    )

    # ── Gemini Matrix ────────────────────────────────────────────────────────
    gemini_model: str = field(
        default_factory=lambda: _get("GEMINI_MODEL", "gemini-3.6-flash")
    )
    gemini_model_flash: str = field(
        default_factory=lambda: _get("GEMINI_MODEL_FLASH", "gemini-3.6-flash")
    )
    gemini_model_lite: str = field(
        default_factory=lambda: _get("MEMORY_MODEL", "openrouter/google/gemini-3.5-flash-lite")
    )
    gemini_model_thinking: str = field(
        default_factory=lambda: _get("GEMINI_MODEL_THINKING", "gemini-3.6-flash")
    )

    # ── Anthropic Claude Matrix ──────────────────────────────────────────────
    # Haiku: Fast, cheap ($1.00/1M) for normal chat, greetings, Q&A.
    chat_model_haiku: str = field(
        default_factory=lambda: _get("CHAT_MODEL_HAIKU", "claude-haiku-4-5-20251001")
    )
    # Sonnet: Powerful reasoning ($3.00/1M) for complex accounting, valuation, PDFs, Excel.
    chat_model_sonnet: str = field(
        default_factory=lambda: _get("CHAT_MODEL_SONNET", "claude-sonnet-5")
    )
    # Default chat model for legacy references
    chat_model: str = field(
        default_factory=lambda: _get("CHAT_MODEL", "gemini-3.6-flash" if _get("LLM_PROVIDER", "gemini").lower() == "gemini" else "claude-sonnet-5")
    )

    # ── Memory Model ─────────────────────────────────────────────────────────
    memory_model: str = field(
        default_factory=lambda: _get("MEMORY_MODEL", "gemini-3.6-flash" if _get("LLM_PROVIDER", "gemini").lower() == "gemini" else "claude-haiku-4-5-20251001")
    )

    # ── Local Embedding Model (sentence-transformers, FREE) ──────────────────
    embedding_model: str = field(
        default_factory=lambda: _get("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
    )

    def as_mem0_llm_dict(self) -> dict:
        """Mem0 internal LLM config for background memory fact extraction."""
        return {
            "provider": "openai",
            "config": {
                "model": "auto",
                "api_key": self.freellmapi_api_key,
                "openai_base_url": self.freellmapi_base_url,
                "temperature": 0.1,
                "max_tokens": 1024,
            },
        }

    def as_mem0_embedder_dict(self) -> dict:
        provider = _get("EMBEDDER_PROVIDER", "fastembed").lower()
        if provider == "fastembed":
            return {
                "provider": "fastembed",
                "config": {
                    "model": "BAAI/bge-small-en-v1.5",
                },
            }
        return {
            "provider": "huggingface",
            "config": {
                "model": "BAAI/bge-small-en-v1.5",
            },
        }


@dataclass(frozen=True)
class AgentConfig:
    # ── memory retrieval ──────────────────────────────────────────────────────
    memory_top_k: int = field(default_factory=lambda: int(_get("MEMORY_TOP_K", "5")))
    pii_retention_days: int = field(default_factory=lambda: int(_get("PII_RETENTION_DAYS", "30")))
    sessions_retention_days: int = field(
        default_factory=lambda: int(_get("SESSIONS_RETENTION_DAYS", "90"))
    )
    telemetry_retention_days: int = field(
        default_factory=lambda: int(_get("TELEMETRY_RETENTION_DAYS", "90"))
    )
    audit_log_retention_days: int = field(
        default_factory=lambda: int(_get("AUDIT_LOG_RETENTION_DAYS", "365"))
    )
    blackboard_retention_days: int = field(
        default_factory=lambda: int(_get("BLACKBOARD_RETENTION_DAYS", "30"))
    )
    purge_mem0: bool = field(
        default_factory=lambda: _get("PURGE_MEM0", "false").lower() in ("true", "1", "yes")
    )

    # How many turns to wait before re-fetching memories from Qdrant.
    # In between, the session uses the cached memory list (saves vector search).
    # Set to 1 to always fetch fresh (most accurate but no caching).
    memory_refresh_interval: int = field(
        default_factory=lambda: int(_get("MEMORY_REFRESH_INTERVAL", "3"))
    )

    # How many turns to batch before triggering a Mem0 memory update.
    # The agent also always updates immediately when personal info is detected.
    # Higher = fewer Haiku API calls; lower = more real-time memory updates.
    memory_update_interval: int = field(
        default_factory=lambda: int(_get("MEMORY_UPDATE_INTERVAL", "3"))
    )

    # ── conversation history ──────────────────────────────────────────────────
    # Max user+assistant turn PAIRS to keep in the in-session message list.
    # Older turns are already stored in Qdrant; trimming them cuts input tokens.
    max_history_turns: int = field(
        default_factory=lambda: int(_get("MAX_HISTORY_TURNS", "10"))
    )

    # ── budget / cost control ─────────────────────────────────────────────────
    # Total tokens per day (input + output). 0 = unlimited.
    daily_token_limit: int = field(
        default_factory=lambda: int(_get("DAILY_TOKEN_LIMIT", "0"))
    )
    # Max USD spend per day. 0 = unlimited.
    daily_cost_limit_usd: float = field(
        default_factory=lambda: float(_get("DAILY_COST_LIMIT_USD", "0"))
    )
    # Warn user when budget is this fraction used (0.8 = 80%).
    budget_warn_threshold: float = field(
        default_factory=lambda: float(_get("BUDGET_WARN_THRESHOLD", "0.80"))
    )


@dataclass(frozen=True)
class ToolConfig:
    """Configuration for Ultron's autonomous tool execution engine."""

    # Master switch — set to False to disable all tool execution.
    enabled: bool = field(
        default_factory=lambda: _get("TOOL_EXECUTION_ENABLED", "true").lower() == "true"
    )

    # Max tool call iterations per single user directive.
    max_iterations: int = field(
        default_factory=lambda: int(_get("TOOL_MAX_ITERATIONS", "25"))
    )



    # Command execution timeout (seconds).
    command_timeout: int = field(
        default_factory=lambda: int(_get("TOOL_COMMAND_TIMEOUT", "60"))
    )

    # Python script execution timeout (seconds).
    python_timeout: int = field(
        default_factory=lambda: int(_get("TOOL_PYTHON_TIMEOUT", "120"))
    )

    # Workspace root for file operations.
    workspace_root: str = field(
        default_factory=lambda: _get("TOOL_WORKSPACE_ROOT", str(Path(__file__).resolve().parent))
    )

    # Max output chars returned to Claude per tool call.
    max_output_length: int = field(
        default_factory=lambda: int(_get("TOOL_MAX_OUTPUT_LENGTH", "8000"))
    )


@dataclass(frozen=True)
class EmailConfig:
    """
    Configuration for Ultron's Autonomous Email & Inbox Engine.
    Supports multi-profile IMAP search & reading and SMTP sending.
    """
    enabled: bool = field(default_factory=lambda: _get("EMAIL_ENABLED", "false").lower() in ("true", "1", "yes"))
    imap_host: str = field(default_factory=lambda: _get("EMAIL_IMAP_HOST", "imap.gmail.com"))
    imap_port: int = field(default_factory=lambda: int(_get("EMAIL_IMAP_PORT", "993")))
    smtp_host: str = field(default_factory=lambda: _get("EMAIL_SMTP_HOST", "smtp.gmail.com"))
    smtp_port: int = field(default_factory=lambda: int(_get("EMAIL_SMTP_PORT", "465")))
    use_ssl: bool = field(default_factory=lambda: _get("EMAIL_USE_SSL", "true").lower() in ("true", "1", "yes"))
    default_profile: str = field(default_factory=lambda: _get("EMAIL_DEFAULT_PROFILE", "primary"))

    # Profiles mapping
    work_user: str = field(default_factory=lambda: _get("WORK_EMAIL_USER", ""))
    work_password: str = field(default_factory=lambda: _get("WORK_EMAIL_PASSWORD", ""))

    personal_user: str = field(default_factory=lambda: _get("PERSONAL_EMAIL_USER", ""))
    personal_password: str = field(default_factory=lambda: _get("PERSONAL_EMAIL_PASSWORD", ""))

    secondary_user: str = field(default_factory=lambda: _get("SECONDARY_EMAIL_USER", ""))
    secondary_password: str = field(default_factory=lambda: _get("SECONDARY_EMAIL_PASSWORD", ""))

    drafts_dir: str = field(default_factory=lambda: _get("EMAIL_DRAFTS_DIR", "./data/email_drafts"))


def check_startup_env() -> list[str]:
    """
    Validates environment configuration for configured email and browser features.
    If required .env variables are missing, logs ONE warning naming the variable (never values).
    Returns list of missing variable names.
    """
    import logging
    logger = logging.getLogger("ultron.startup")
    missing_vars = []

    # 1. Email feature check
    email_enabled = os.getenv("EMAIL_ENABLED", "false").lower() in ("true", "1", "yes")

    personal_user = os.getenv("PERSONAL_EMAIL_USER")
    personal_pass = os.getenv("PERSONAL_EMAIL_PASSWORD")
    if personal_user and not personal_pass:
        missing_vars.append("PERSONAL_EMAIL_PASSWORD")
    elif personal_pass and not personal_user:
        missing_vars.append("PERSONAL_EMAIL_USER")
    elif email_enabled and not personal_user:
        missing_vars.append("PERSONAL_EMAIL_USER")
        if not personal_pass:
            missing_vars.append("PERSONAL_EMAIL_PASSWORD")

    work_user = os.getenv("WORK_EMAIL_USER")
    work_pass = os.getenv("WORK_EMAIL_PASSWORD")
    if work_user and not work_pass:
        missing_vars.append("WORK_EMAIL_PASSWORD")
    elif work_pass and not work_user:
        missing_vars.append("WORK_EMAIL_USER")

    sec_user = os.getenv("SECONDARY_EMAIL_USER")
    sec_pass = os.getenv("SECONDARY_EMAIL_PASSWORD")
    if sec_user and not sec_pass:
        missing_vars.append("SECONDARY_EMAIL_PASSWORD")
    elif sec_pass and not sec_user:
        missing_vars.append("SECONDARY_EMAIL_USER")

    if email_enabled:
        if not os.getenv("EMAIL_IMAP_HOST"):
            missing_vars.append("EMAIL_IMAP_HOST")
        if not os.getenv("EMAIL_SMTP_HOST"):
            missing_vars.append("EMAIL_SMTP_HOST")

    deduped = sorted(list(set(missing_vars)))
    for var in deduped:
        logger.warning(f"Missing required environment variable for configured feature: {var}")

    return deduped


@dataclass(frozen=True)
class ReflectionConfig:
    """
    Configuration for Ultron's autonomous self-learning engine.

    The reflection engine runs a fast Haiku call after every N turns to:
      1. Score response quality (0-10).
      2. Store "LESSON:" memories in ChromaDB when quality is low.
      3. Auto-write new SKILL.md files when quality is high and task was novel.
    """
    # Master switch. Set REFLECTION_ENABLED=false in .env to disable.
    enabled: bool = field(
        default_factory=lambda: _get("REFLECTION_ENABLED", "true").lower() == "true"
    )
    # Only reflect once every N turns to keep costs negligible.
    cooldown_turns: int = field(
        default_factory=lambda: int(_get("REFLECTION_COOLDOWN_TURNS", "2"))
    )
    # Store a lesson memory when response score is at or below this value (0-10).
    max_fail_score: int = field(
        default_factory=lambda: int(_get("REFLECTION_MAX_FAIL_SCORE", "5"))
    )
    # Only auto-write a new skill when score is at or above this value (0-10).
    min_skill_score: int = field(
        default_factory=lambda: int(_get("REFLECTION_MIN_SKILL_SCORE", "8"))
    )
    # Prefix for auto-generated skill folder names.
    auto_skill_prefix: str = field(
        default_factory=lambda: _get("REFLECTION_AUTO_SKILL_PREFIX", "auto_")
    )


@dataclass(frozen=True)
class MCPConfig:
    """Configuration for Model Context Protocol (MCP) servers (Layer 3)."""
    enabled: bool = field(
        default_factory=lambda: _get("MCP_ENABLED", "true").lower() == "true"
    )
    mcp_servers_dir: str = field(
        default_factory=lambda: _get("MCP_SERVERS_DIR", "./mcp_servers")
    )


@dataclass(frozen=True)
class TelemetryConfig:
    """Configuration for Layer 8 Telemetry & Audit DB."""
    enabled: bool = field(
        default_factory=lambda: _get("TELEMETRY_ENABLED", "true").lower() == "true"
    )
    db_path: str = field(
        default_factory=lambda: _get("TELEMETRY_DB_PATH", "./data/telemetry.db")
    )




# ── custom prompts ────────────────────────────────────────────────────────────

CUSTOM_FACT_EXTRACTION_PROMPT = """
You are an expert at extracting meaningful, durable facts from a conversation.

Your task is to identify only facts that are worth remembering long-term about the USER.
Focus on:
  - Personal details (name, age, location, occupation, industry)
  - Preferences, likes, and dislikes (food, hobbies, media, tools, workflows)
  - Professional goals, skills, and experience
  - Job hunting or client hunting context (target roles, industries, locations)
  - Financial or accounting context (software used, business type, pain points)
  - Any explicit corrections the user makes to previously stated facts

Rules:
  1. Extract ONLY facts about the USER, not the assistant.
  2. State each fact as a concise, standalone sentence.
  3. If the user explicitly says they no longer like or believe something, capture the UPDATED state, not the old one.
  4. Do NOT extract transient conversational fillers ("thanks", "ok", "sounds good", etc.).
Respond ONLY with a JSON object containing a "facts" list, e.g.:
{"facts": ["User's name is Alice.", "User works in accounting.", "User is looking for remote finance roles."]}
"""


CUSTOM_MEMORY_UPDATE_PROMPT = """
You are an expert memory manager. Your job is to keep a user's memory store accurate and up-to-date.

You will receive:
  - EXISTING_MEMORIES: the current set of stored facts (each with an id and text).
  - NEW_FACTS: freshly extracted facts from the latest conversation turn.

Your task is to decide, for each new fact, which of the following operations to perform:
  - ADD    → the fact is genuinely new and should be added.
  - UPDATE → the fact contradicts or refines an existing memory (provide the id to update).
  - DELETE → an existing memory is now known to be false or explicitly overridden (provide the id to delete).
  - NONE   → the fact is already accurately captured in an existing memory; do nothing.

Rules:
  1. Prefer UPDATE/DELETE over ADD when a contradiction or correction is detected.
  2. A user saying "I don't like X anymore, I like Y now" should:
       - DELETE or UPDATE the "likes X" memory.
       - ADD or UPDATE to record "likes Y".
  3. A user saying "I no longer work at X, I now work at Y" should UPDATE the job memory.
  4. Do NOT duplicate already-correct memories.
  5. Be conservative: when in doubt, choose NONE rather than adding noise.

Respond ONLY with a JSON array of operation objects, e.g.:
[
  {"operation": "ADD",    "text": "User is targeting CFO roles in fintech."},
  {"operation": "UPDATE", "id": "<existing_memory_id>", "text": "User now uses QuickBooks instead of Xero."},
  {"operation": "DELETE", "id": "<existing_memory_id>"}
]
"""


# ── convenience builder ───────────────────────────────────────────────────────

def build_mem0_config(vector_store: VectorStoreConfig, llm: LLMConfig) -> dict:
    """
    Assemble the full configuration dict for mem0.Memory().

    Custom prompts are injected here so Mem0's internal fact-extraction
    and memory-update steps use our domain-specific instructions.
    """
    return {
        "vector_store": vector_store.as_mem0_dict(),
        "llm": llm.as_mem0_llm_dict(),
        "embedder": llm.as_mem0_embedder_dict(),
        "custom_fact_extraction_prompt": CUSTOM_FACT_EXTRACTION_PROMPT,
        "custom_update_memory_prompt": CUSTOM_MEMORY_UPDATE_PROMPT,
        "version": "v1.1",
    }

