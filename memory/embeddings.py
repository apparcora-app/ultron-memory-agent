"""
embeddings.py — Resilient Embedding Abstraction Layer for Ultron Memory Agent.

Supports fast CPU embeddings, SentenceTransformers, and ONNX Runtime providers
with automated graceful degradation when local ML binary kernels conflict.
"""

from __future__ import annotations

import logging
from abc import abstractmethod
from typing import Protocol, runtime_checkable

logger = logging.getLogger("ultron.memory.embeddings")


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Abstract contract for vector embeddings."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Vector output dimension."""
        ...

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate normalized vector embeddings for a list of strings."""
        ...

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """Generate embedding vector for a search query string."""
        ...


class SentenceTransformerProvider:
    """Standard HuggingFace SentenceTransformers embedding provider."""

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> None:
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self._model = SentenceTransformer(model_name)
        self._dim = self._model.get_sentence_embedding_dimension()

    @property
    def dimension(self) -> int:
        return int(self._dim)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        embeddings = self._model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]


class FastEmbedProvider:
    """Zero-PyTorch embedding provider powered by ONNX Runtime.

    Extremely lightweight (<50MB wheel), zero GPU/MSVC compiler dependency.
    """

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5") -> None:
        try:
            from fastembed import TextEmbedding
        except ImportError as exc:
            raise ImportError(
                "fastembed is required. Install via `pip install fastembed`"
            ) from exc

        self.model_name = model_name
        self._model = TextEmbedding(model_name=model_name)
        self._dimension = 384 if "small" in model_name or "MiniLM" in model_name else 768

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        embeddings = self._model.embed(texts)
        return [arr.tolist() for arr in embeddings]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]


def get_default_embedding_provider(
    preferred_model: str = "sentence-transformers/all-MiniLM-L6-v2",
) -> EmbeddingProvider:
    """Factory creating the most resilient available embedding provider."""
    # 1. Try FastEmbed if available
    try:
        import fastembed  # noqa: F401

        logger.info("Initializing FastEmbed ONNX provider")
        return FastEmbedProvider()
    except ImportError:
        pass

    # 2. Try SentenceTransformers
    try:
        logger.info("Initializing SentenceTransformer provider: %s", preferred_model)
        return SentenceTransformerProvider(preferred_model)
    except Exception as exc:
        logger.warning(
            "SentenceTransformer failed to initialize: %s. Falling back.", exc
        )
        raise RuntimeError(f"Could not initialize any embedding provider: {exc}") from exc
