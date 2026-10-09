"""rag/store.py - Shared embedder + `rag_docs` collection access.

Only touches the `rag_docs` collection. Never reads/writes ExpeL data
(`ultron_trajectories`) or any other collection in the same Chroma store.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import List

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

from rag import config  # noqa: E402


@lru_cache(maxsize=1)
def get_embedder():
    """Load the single fixed embedding model named in rag/config.py."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(config.EMBEDDING_MODEL_NAME)


def embed(texts: List[str]) -> List[List[float]]:
    """Embed texts with the fixed model (L2-normalized for cosine space)."""
    vecs = get_embedder().encode(
        texts, normalize_embeddings=True, show_progress_bar=False, batch_size=16
    )
    return [v.tolist() for v in vecs]


def get_collection():
    """Open (or create) `rag_docs`. Refuses to run if the embedding model changed."""
    import chromadb

    config.CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(config.CHROMA_PATH))
    col = client.get_or_create_collection(
        name=config.COLLECTION_NAME,
        metadata={
            "hnsw:space": "cosine",
            "embedding_model": config.EMBEDDING_MODEL_NAME,
        },
        embedding_function=None,  # we always pass our own embeddings
    )
    stored = (col.metadata or {}).get("embedding_model")
    if stored != config.EMBEDDING_MODEL_NAME:
        raise RuntimeError(
            f"rag_docs was built with embedding model {stored!r} but config says "
            f"{config.EMBEDDING_MODEL_NAME!r}. Re-ingest into a fresh collection."
        )
    return col
