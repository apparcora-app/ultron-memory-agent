"""
test_qdrant_store.py — Rigorous Verification Suite for Local Embedded Qdrant Storage.

Verifies:
1. In-process initialization of LocalQdrantStore without background daemons or external servers.
2. Accurate point insertion, vector search, score calculation, and metadata filtering.
3. Deletion and collection lifecycle management.
4. Seamless integration with VectorStoreConfig and Mem0 configuration dicts.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from qdrant_client.models import Distance

from core.config import VectorStoreConfig
from memory.qdrant_store import LocalQdrantStore


class TestLocalQdrantStore:
    """Test suite ensuring rock-solid stability and empirical correctness of LocalQdrantStore."""

    @pytest.fixture
    def temp_store_dir(self) -> Path:
        """Create an isolated temporary directory for Qdrant storage."""
        tmp = tempfile.mkdtemp()
        try:
            yield Path(tmp)
        finally:
            norm = str(Path(tmp).resolve())
            from memory.qdrant_store import _CLIENTS
            c = _CLIENTS.pop(norm, None)
            if c:
                try:
                    c.close()
                except Exception:
                    pass
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_initialization_creates_collection(self, temp_store_dir: Path) -> None:
        """Verify collection auto-creation with custom dimensionality."""
        store = LocalQdrantStore(
            path=temp_store_dir,
            collection_name="test_col_init",
            vector_size=128,
            distance=Distance.COSINE,
        )
        assert store.count() == 0
        assert store.collection_name == "test_col_init"
        assert store.vector_size == 128

    def test_upsert_and_similarity_search(self, temp_store_dir: Path) -> None:
        """Verify upserting vectors and finding exact nearest neighbors."""
        store = LocalQdrantStore(
            path=temp_store_dir,
            collection_name="test_search",
            vector_size=4,
            distance=Distance.COSINE,
        )

        # Points
        points = [
            {
                "id": 1,
                "vector": [1.0, 0.0, 0.0, 0.0],
                "payload": {"topic": "accounting", "priority": "high"},
            },
            {
                "id": 2,
                "vector": [0.0, 1.0, 0.0, 0.0],
                "payload": {"topic": "development", "priority": "medium"},
            },
            {
                "id": 3,
                "vector": [0.9, 0.1, 0.0, 0.0],
                "payload": {"topic": "accounting", "priority": "low"},
            },
        ]
        store.upsert(points)
        assert store.count() == 3

        # Search for vector closest to [1.0, 0.0, 0.0, 0.0]
        hits = store.search(query_vector=[1.0, 0.0, 0.0, 0.0], limit=2)
        assert len(hits) == 2
        # Nearest should be point 1 (cosine sim ~ 1.0)
        assert hits[0]["id"] == 1
        assert hits[0]["payload"]["topic"] == "accounting"
        assert hits[0]["score"] > 0.99

        # Filtered search: accounting only
        filtered_hits = store.search(
            query_vector=[0.0, 1.0, 0.0, 0.0],
            limit=2,
            filter_dict={"topic": "development"},
        )
        assert len(filtered_hits) == 1
        assert filtered_hits[0]["id"] == 2
        assert filtered_hits[0]["payload"]["topic"] == "development"

    def test_deletion_and_lifecycle(self, temp_store_dir: Path) -> None:
        """Verify deletion of specific points and drops."""
        store = LocalQdrantStore(
            path=temp_store_dir,
            collection_name="test_del",
            vector_size=2,
        )
        store.upsert([
            {"id": 10, "vector": [0.5, 0.5], "payload": {}},
            {"id": 20, "vector": [-0.5, -0.5], "payload": {}},
        ])
        assert store.count() == 2

        store.delete([10])
        assert store.count() == 1

        hits = store.search(query_vector=[0.5, 0.5], limit=1)
        assert hits[0]["id"] == 20

    def test_vector_store_config_defaults_to_qdrant(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify VectorStoreConfig defaults to Qdrant without ChromaDB hacks."""
        monkeypatch.delenv("VECTOR_STORE_PROVIDER", raising=False)
        monkeypatch.delenv("VECTOR_STORE_PATH", raising=False)

        cfg = VectorStoreConfig()
        assert cfg.provider == "qdrant"
        assert cfg.path == "./data/qdrant"

        mem0_block = cfg.as_mem0_dict()
        assert mem0_block["provider"] == "qdrant"
        assert mem0_block["config"]["on_disk"] is True
        assert mem0_block["config"]["path"] == "./data/qdrant"
        assert mem0_block["config"]["embedding_model_dims"] == 384
