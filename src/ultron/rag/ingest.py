"""rag/ingest.py - Load, chunk, redact, embed and store documents in `rag_docs`.

Pipeline per file/page:  load -> redact -> chunk (~500 tok, 50 overlap)
                         -> redact each chunk again -> embed -> upsert.

Re-ingestion is idempotent: chunk ids are deterministic hashes of
(source, page, chunk index, redacted text) and are upserted; chunks that
belong to a file but are no longer produced (file edited/shrunk) are removed.
"""
from __future__ import annotations

import hashlib
import sys
from collections.abc import Iterator
from pathlib import Path

from ultron.rag import config
from ultron.rag.store import embed, get_collection, get_embedder

# Shared PII redaction function used across Ultron Prime.
sys.path.insert(0, str(config.ROOT_DIR))
from pii_redaction import safe_redact_text  # noqa: E402


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def iter_source_files(source_dir: Path) -> list[Path]:
    """Return supported files under source_dir (sorted, non-recursive symlink-safe)."""
    source_dir = Path(source_dir)
    if not source_dir.is_dir():
        raise FileNotFoundError(f"RAG source directory not found: {source_dir}")
    root = source_dir.resolve()
    files = []
    for p in sorted(source_dir.rglob("*")):
        if p.is_file() and p.suffix.lower() in config.SUPPORTED_EXTENSIONS:
            # Refuse anything that resolves outside the source dir (symlink escape).
            if root in p.resolve().parents:
                files.append(p)
    return files


def load_pages(path: Path) -> Iterator[tuple[int, str]]:
    """Yield (page_number, text). Text/markdown files are a single page (1)."""
    ext = path.suffix.lower()
    if ext in (".txt", ".md"):
        yield 1, path.read_text(encoding="utf-8", errors="replace")
    elif ext == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        for i, page in enumerate(reader.pages, start=1):
            yield i, page.extract_text() or ""
    else:  # pragma: no cover - guarded by iter_source_files
        raise ValueError(f"Unsupported file type: {path}")


# --------------------------------------------------------------------------- #
# Chunking (token-based using the embedding model's own tokenizer)
# --------------------------------------------------------------------------- #
def chunk_text(
    text: str,
    chunk_tokens: int = config.CHUNK_TOKENS,
    overlap: int = config.CHUNK_OVERLAP_TOKENS,
) -> list[str]:
    """Split text into windows of `chunk_tokens` tokens with `overlap` overlap.

    Slices the ORIGINAL text via tokenizer offsets, so casing/whitespace survive.
    """
    if overlap >= chunk_tokens:
        raise ValueError("overlap must be smaller than chunk_tokens")
    text = text.strip()
    if not text:
        return []
    tok = get_embedder().tokenizer
    enc = tok(text, add_special_tokens=False, return_offsets_mapping=True,
              truncation=False, verbose=False)
    offsets = enc["offset_mapping"]
    n = len(offsets)
    if n == 0:
        return []
    step = chunk_tokens - overlap
    chunks: list[str] = []
    start = 0
    while start < n:
        end = min(start + chunk_tokens, n)
        piece = text[offsets[start][0]: offsets[end - 1][1]].strip()
        if piece:
            chunks.append(piece)
        if end >= n:
            break
        start += step
    return chunks


# --------------------------------------------------------------------------- #
# Ingestion
# --------------------------------------------------------------------------- #
def _chunk_id(source: str, page: int, idx: int, text: str) -> str:
    h = hashlib.sha256(f"{source}|{page}|{idx}|{text}".encode()).hexdigest()
    return h[:32]


def build_chunks(path: Path, source_dir: Path) -> list[dict]:
    """Produce redacted chunk records (id, text, metadata) for one file."""
    source = path.resolve().relative_to(Path(source_dir).resolve()).as_posix()
    records: list[dict] = []
    for page_no, raw in load_pages(path):
        # Pre-pass: redact the whole page so PII cannot be split across chunk edges.
        page_text = safe_redact_text(raw)
        for idx, piece in enumerate(chunk_text(page_text)):
            clean = safe_redact_text(piece)  # per-chunk redaction (required, pre-embedding)
            if not clean.strip():
                continue
            cid = _chunk_id(source, page_no, idx, clean)
            text_with_context = f"Document: {source}\n\n{clean}"
            records.append({
                "id": cid,
                "text": text_with_context,
                "metadata": {
                    "source": source,
                    "page": page_no,
                    "chunk_index": idx,
                    "chunk_id": cid,
                },
            })
    return records


def ingest(source_dir: Path = config.SOURCE_DIR) -> dict[str, int]:
    """Ingest all supported files. Safe to run repeatedly (no duplicates)."""
    col = get_collection()
    files = iter_source_files(source_dir)
    total_chunks = 0
    removed = 0
    for path in files:
        records = build_chunks(path, source_dir)
        source = records[0]["metadata"]["source"] if records else (
            path.resolve().relative_to(Path(source_dir).resolve()).as_posix())
        if records:
            texts = [r["text"] for r in records]
            col.upsert(
                ids=[r["id"] for r in records],
                documents=texts,
                embeddings=embed(texts),
                metadatas=[r["metadata"] for r in records],
            )
        # Remove stale chunks of this file that are no longer produced.
        keep = {r["id"] for r in records}
        existing = col.get(where={"source": source}, include=[])["ids"]
        stale = [i for i in existing if i not in keep]
        if stale:
            col.delete(ids=stale)
            removed += len(stale)
        total_chunks += len(records)
    return {"files": len(files), "chunks_processed": total_chunks,
            "stale_removed": removed, "collection_count": col.count()}


if __name__ == "__main__":
    stats = ingest()
    print(f"[ingest] {stats}")
    col = get_collection()
    sample = col.get(limit=2, include=["documents", "metadatas"])
    for i, (doc, meta) in enumerate(zip(sample["documents"], sample["metadatas"], strict=False), 1):
        print(f"\n--- sample chunk {i} ---\nmetadata: {meta}\ntext: {doc[:300]!r}")
