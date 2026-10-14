"""
qdrant_store.py — Lightweight, High-Performance Embedded Qdrant Storage for Ultron.

Provides a robust, zero-daemon, pure Python vector store wrapper powered by
qdrant-client's embedded storage engine. Eliminates ChromaDB Rust panics and
raw SQLite migration corruption hacks.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

logger = logging.getLogger(__name__)

_CLIENTS: dict[str, QdrantClient] = {}


class LocalQdrantStore:
    """
    Local embedded vector store built on top of Qdrant's embedded storage.

    Runs entirely in-process on disk without Docker, server daemons, or network ports.
    Supports cosine, dot product, or euclidean vector searches with metadata filtering.
    """

    def __init__(
        self,
        path: str | Path = "./data/qdrant",
        collection_name: str = "ultron_vectors",
        vector_size: int = 384,
        distance: Distance = Distance.COSINE,
    ) -> None:
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection_name
        self.vector_size = vector_size
        self.distance = distance

        norm_path = str(self.path.resolve())
        if norm_path not in _CLIENTS:
            try:
                _CLIENTS[norm_path] = QdrantClient(path=norm_path)
            except Exception as e:
                if "already accessed by another instance" in str(e) or "lock" in str(e).lower():
                    logger.warning(
                        "Storage folder '%s' locked by another active Ultron process. Falling back to shared in-memory store for this worker session.",
                        norm_path,
                    )
                    _CLIENTS[norm_path] = QdrantClient(":memory:")
                else:
                    raise
        self.client = _CLIENTS[norm_path]
        self._ensure_collection()

    def close(self) -> None:
        """Close client connection and release file locks."""
        norm_path = str(self.path.resolve())
        client = _CLIENTS.pop(norm_path, None)
        if client:
            try:
                client.close()
            except Exception:
                pass

    def _ensure_collection(self) -> None:
        """Create collection if it does not already exist."""
        existing = [c.name for c in self.client.get_collections().collections]
        if self.collection_name not in existing:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.vector_size, distance=self.distance),
            )
            logger.info("Created local Qdrant collection '%s' (dim=%d)", self.collection_name, self.vector_size)

    def count(self) -> int:
        """Return total number of points in the collection."""
        res = self.client.count(collection_name=self.collection_name)
        return res.count

    def upsert(
        self,
        points: Sequence[dict[str, Any]],
    ) -> None:
        """
        Upsert a batch of points.

        Each item in points should have:
            - id: int or str (UUID)
            - vector: list[float]
            - payload: dict[str, Any] (optional)
        """
        qdrant_points: list[PointStruct] = []
        for p in points:
            pid = p["id"]
            vec = p["vector"]
            payload = p.get("payload", {})
            qdrant_points.append(PointStruct(id=pid, vector=vec, payload=payload))

        if qdrant_points:
            self.client.upsert(
                collection_name=self.collection_name,
                points=qdrant_points,
            )

    def search(
        self,
        query_vector: list[float],
        limit: int = 5,
        filter_dict: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search for nearest neighbor vectors.

        Returns a list of dicts with:
            - id: point ID
            - score: similarity score
            - payload: stored metadata dictionary
        """
        query_filter = None
        if filter_dict:
            conds: list[Any] = [
                FieldCondition(key=k, match=MatchValue(value=v))
                for k, v in filter_dict.items()
            ]
            query_filter = Filter(must=conds)

        results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=limit,
            query_filter=query_filter,
        )

        output: list[dict[str, Any]] = []
        for hit in results.points:
            output.append({
                "id": hit.id,
                "score": hit.score,
                "payload": hit.payload or {},
            })
        return output

    def delete(self, point_ids: Sequence[int | str]) -> None:
        """Delete specific points by ID."""
        if not point_ids:
            return
        from qdrant_client.models import PointIdsList
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=PointIdsList(points=list(point_ids)),
        )

    def delete_collection(self) -> None:
        """Drop the entire collection."""
        self.client.delete_collection(collection_name=self.collection_name)
