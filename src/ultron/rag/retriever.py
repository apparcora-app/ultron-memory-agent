"""rag/retriever.py - Semantic retrieval over the `rag_docs` collection."""
from __future__ import annotations

from ultron.rag import config
from ultron.rag.store import embed, get_collection

MAX_K = 50
MAX_QUERY_CHARS = 2000


def retrieve(query: str, k: int = 5) -> list[dict]:
    """Return the top-k chunks for `query`.

    Each result: {"text", "source", "page", "chunk_id", "score"}
    where score = cosine similarity (higher is better, 1.0 = identical).
    """
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string")
    if not isinstance(k, int) or isinstance(k, bool) or not (1 <= k <= MAX_K):
        raise ValueError(f"k must be an integer between 1 and {MAX_K}")
    query = query.strip()[:MAX_QUERY_CHARS]

    col = get_collection()
    n = col.count()
    if n == 0:
        return []
    qvec = embed([config.QUERY_PREFIX + query])[0]
    res = col.query(
        query_embeddings=[qvec],
        n_results=min(k, n),
        include=["documents", "metadatas", "distances"],
    )
    out: list[dict] = []
    for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0], strict=False):
        out.append({
            "text": doc,
            "source": meta.get("source"),
            "page": meta.get("page"),
            "chunk_id": meta.get("chunk_id"),
            "score": round(1.0 - float(dist), 4),  # cosine distance -> similarity
        })
    return out


if __name__ == "__main__":
    for q in (
        "How many vacation days do employees get per year?",
        "How do I roll back a failed production release?",
        "How long are customer database backups kept?",
    ):
        print(f"\nQUERY: {q}")
        for r in retrieve(q, k=3):
            print(f"  [{r['score']:.3f}] {r['source']} (p{r['page']}) :: {r['text'][:110]!r}")
