# 🧠 Ultron Memory Agent

A modular Python AI agent with **persistent long-term memory** built on [Mem0](https://github.com/mem0ai/mem0) and [Qdrant](https://qdrant.tech/).

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                        main.py                          │
│              (Rich CLI + slash commands)                 │
└───────────────────────┬─────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────┐
│                       agent.py                          │
│            MemoryAgent  ←→  OpenAI chat API             │
│                                                         │
│  Phase 1 (before reply): search() → inject into prompt  │
│  Phase 2  (after reply): add()   → extract & update     │
└───────────────────────┬─────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────┐
│                  memory_manager.py                      │
│           MemoryManager  wraps  mem0.Memory             │
│       (exposes .mem for direct Mem0/Qdrant access)      │
└───────────────────────┬─────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────┐
│                      Qdrant                             │
│       Persistent vector store (Docker container)        │
│       Dashboard → http://localhost:6333/dashboard       │
└─────────────────────────────────────────────────────────┘
```

### Two-Phase Memory Pipeline

| Phase | When | What happens |
|-------|------|--------------|
| **1 — Retrieve** | Before LLM call | Semantic search fetches top-K relevant memories → injected into system prompt |
| **2 — Update** | After LLM reply | Latest turn fed to Mem0 → custom prompts extract facts → ADD / UPDATE / DELETE ops applied to Qdrant |

### Custom Prompts

Two custom prompts override Mem0's defaults (defined in [`config.py`](config.py)):

- **`CUSTOM_FACT_EXTRACTION_PROMPT`** — extracts only durable, user-specific facts; ignores conversational filler.
- **`CUSTOM_MEMORY_UPDATE_PROMPT`** — explicitly handles contradiction/correction cases (e.g. "I don't like X anymore, I like Y now") by choosing UPDATE/DELETE over blind ADD.

---

## Quick Start

### 1 — Prerequisites

- Python 3.10+
- Docker Desktop (for Qdrant)
- An OpenAI API key

### 2 — Clone & install

```bash
git clone <your-repo-url>
cd mem0_agent

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 3 — Configure environment

```bash
cp .env.example .env
# Edit .env and set OPENAI_API_KEY
```

### 4 — Start Qdrant

```bash
docker compose up -d
# Verify: http://localhost:6333/dashboard
```

### 5 — Run the agent

```bash
# Default user
python main.py

# Named user (separate memory namespace)
python main.py --user alice

# Debug mode (prints retrieved memories each turn)
python main.py --debug
```

---

## Chat Commands

| Command | Description |
|---------|-------------|
| `/memories` | List every stored memory for the current user |
| `/clear` | Wipe in-session message history (long-term memories intact) |
| `/forget <id>` | Delete a memory by its ID prefix |
| `/help` | Show command list |
| `/quit` | Exit |

---

## Project Structure

```
mem0_agent/
├── main.py              # CLI entry point (Rich UI + slash commands)
├── agent.py             # MemoryAgent class (two-phase pipeline)
├── memory_manager.py    # Thin Mem0 wrapper with direct Qdrant access
├── config.py            # Config loader, dataclasses, custom prompts
├── requirements.txt
├── docker-compose.yml   # Qdrant service
├── .env.example         # Environment variable template
└── .gitignore
```

---

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | *(required)* | OpenAI API key |
| `QDRANT_HOST` | `localhost` | Qdrant host |
| `QDRANT_PORT` | `6333` | Qdrant REST port |
| `CHAT_MODEL` | `gpt-4o-mini` | Model for chat responses |
| `MEMORY_MODEL` | `gpt-4o-mini` | Model for Mem0 fact extraction |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | OpenAI embedding model |
| `MEMORY_TOP_K` | `5` | Number of memories injected per turn |

---

## Extending the Agent

### Swap the vector database

Edit `QdrantConfig.as_mem0_dict()` in [`config.py`](config.py). Mem0 supports pgvector, Pinecone, Weaviate, Chroma, and more — same interface, different provider string.

### Swap the LLM

Change `CHAT_MODEL` / `MEMORY_MODEL` in `.env`. For non-OpenAI providers, update `LLMConfig.as_mem0_llm_dict()`.

### Direct Qdrant access

```python
from agent import MemoryAgent
agent = MemoryAgent(user_id="alice")

# Full Qdrant client available via:
qdrant_client = agent.memory_manager.mem.vector_store.client
collections = qdrant_client.get_collections()
```

### Multi-user support

Pass different `--user` flags or instantiate multiple `MemoryAgent(user_id=...)` objects — each user's memories are isolated in Qdrant by the `user_id` payload filter.

---

## How Memory Update Works (Under the Hood)

```
User says: "I don't like pizza anymore, I like pasta now."
                       │
              Mem0 fact extraction
                       │
          ["User likes pasta.", "User no longer likes pizza."]
                       │
              Mem0 memory update
                       │
        ┌──────────────┼──────────────┐
        │              │              │
      DELETE         UPDATE          ADD
  "User likes     "User's fav    "User likes
    pizza"          food: pasta"    pasta"
```

The custom `CUSTOM_MEMORY_UPDATE_PROMPT` explicitly instructs the LLM to prefer DELETE/UPDATE over ADD when it detects a contradiction, reducing memory bloat.
