# Quick Task: Embedded Qdrant Migration & Elimination of Chroma SQLite Hacks

## Objective
Drop fragile raw SQLite deletion hacks and make embedded, on-disk Qdrant (`LocalQdrantStore`) the primary, robust vector store provider across Ultron:
1. Create `memory/qdrant_store.py` (`LocalQdrantStore`) wrapping embedded `QdrantClient(path=...)` for pure on-disk vector storage with cosine distance search, metadata filtering, and upsert/delete operations.
2. Update `core/config.py`:
   - Change `VectorStoreConfig.provider` default from `"chroma"` to `"qdrant"` (`VECTOR_STORE_PATH` defaults to `./data/qdrant`).
   - Wire Mem0 configuration dict to use local embedded Qdrant seamlessly.
3. Update `memory/memory_manager.py`:
   - Keep Chroma fallback for backward compatibility if explicitly configured, but bypass fragile `_preflight_sanitize_chroma` when `provider == "qdrant"`.
4. Add comprehensive automated tests in `tests/test_qdrant_store.py` validating:
   - Collection initialization in an isolated temp directory.
   - Vector upsert, cosine nearest neighbor search, and payload retrieval.
   - Seamless integration with `MemoryManager` / `VectorStoreConfig`.
5. Verify with terminal execution and run Ruff checks.
