"""rag/config.py - Single source of truth for RAG settings.

The embedding model is FIXED here. Changing it requires re-ingesting into a
fresh collection (vectors from different models are not comparable).
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]

# --- Embedding (ONE fixed model) -------------------------------------------
# 512-token context window (all-MiniLM-L6-v2 truncates at 256, which would
# silently cut 500-token chunks).
EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"

# --- ChromaDB (existing store; NEW collection, separate from ExpeL data) ----
CHROMA_PATH = Path(os.environ.get("RAG_CHROMA_PATH", ROOT_DIR / "data" / "chroma"))
COLLECTION_NAME = "rag_docs"

# --- Source docs ------------------------------------------------------------
SOURCE_DIR = Path(os.environ.get("RAG_SOURCE_DIR", ROOT_DIR / "data" / "rag_source"))
SUPPORTED_EXTENSIONS = (".txt", ".md", ".pdf")

# --- Chunking (measured in tokens of the embedding model's tokenizer) -------
CHUNK_TOKENS = 500
CHUNK_OVERLAP_TOKENS = 50

# bge models retrieve best when queries (not documents) carry this prefix.
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
