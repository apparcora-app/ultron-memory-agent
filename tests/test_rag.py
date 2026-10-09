"""tests/test_rag.py - RAG ingestion / retrieval / pipeline tests.

Uses an isolated temporary ChromaDB (never touches data/chroma or any ExpeL data).
The sample corpus is data/rag_source/ (leave_policy.txt contains FAKE PII on purpose).
"""
import re

import pytest

from rag import config

SSN = "123-45-6789"
CARD = "4111 1111 1111 1111"
EMAIL = "jane.roe@ultron-example.com"
PII_PATTERNS = [
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
]


@pytest.fixture(scope="module")
def rag_env(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setattr(config, "CHROMA_PATH", tmp_path_factory.mktemp("chroma_rag_test"))
    from rag.ingest import ingest
    from rag.store import get_collection

    stats = ingest(config.SOURCE_DIR)
    yield {"stats": stats, "col": get_collection()}
    mp.undo()


def test_ingest_is_idempotent(rag_env):
    from rag.ingest import ingest

    before = rag_env["col"].count()
    assert before > 0
    ingest(config.SOURCE_DIR)
    assert rag_env["col"].count() == before


@pytest.mark.parametrize(
    "query, expected_source, expected_text",
    [
        ("How many vacation days do employees get per year?", "leave_policy.txt", "18 days"),
        ("How do I roll back a failed production release?", "deployment_guide.md", "make rollback"),
        ("How long are customer database backups kept?", "security_handbook.pdf", "35 days"),
    ],
)
def test_correct_chunk_retrieved(rag_env, query, expected_source, expected_text):
    from rag.retriever import retrieve

    results = retrieve(query, k=3)
    top = results[0]
    assert top["source"] == expected_source
    assert expected_text in top["text"]
    assert top["page"] >= 1 and top["chunk_id"]


def test_pdf_page_metadata(rag_env):
    from rag.retriever import retrieve

    top = retrieve("How long are customer database backups kept?", k=1)[0]
    assert top["page"] == 2  # backups sentence lives on PDF page 2


def test_out_of_scope_says_idk_without_calling_llm(rag_env):
    from rag.pipeline import ask

    calls = []
    state = ask("What is the capital of France?", llm=lambda p, s: calls.append((p, s)) or "Paris")
    assert "don't know" in state["answer"].lower()
    assert "Paris" not in state["answer"]
    assert calls == []  # guard rail: no LLM call when nothing relevant was retrieved


def test_in_scope_prompt_has_rule_context_and_cites_source(rag_env):
    from rag.pipeline import SYSTEM_PROMPT, ask

    seen = {}

    def fake_llm(prompt, system):
        seen["prompt"], seen["system"] = prompt, system
        return "Employees get 18 vacation days per year."  # forgot to cite on purpose

    state = ask("How many vacation days do employees get per year?", llm=fake_llm)
    assert "Answer only from the context. If the answer is not there, say you don't know." in seen["system"]
    assert seen["system"] == SYSTEM_PROMPT
    assert "18 days" in seen["prompt"] and "leave_policy.txt" in seen["prompt"]
    assert "leave_policy.txt" in state["answer"]  # citation enforced by the node


def test_graph_has_retrieve_before_agent():
    from rag.pipeline import build_graph

    edges = {(e.source, e.target) for e in build_graph(llm=lambda p, s: "x").get_graph().edges}
    assert ("__start__", "retrieve") in edges
    assert ("retrieve", "agent") in edges
    assert ("agent", "__end__") in edges


def test_no_pii_stored_in_rag_docs(rag_env):
    data = rag_env["col"].get(include=["documents", "metadatas"])
    assert data["documents"], "collection unexpectedly empty"
    blob = "\n".join(data["documents"]) + "\n" + str(data["metadatas"])
    for raw in (SSN, CARD, EMAIL):
        assert raw not in blob
    for pat in PII_PATTERNS:
        assert not pat.search(blob), f"PII pattern leaked: {pat.pattern}"
    assert "[REDACTED_SSN]" in blob  # proves redaction ran rather than the text being absent


def test_retrieve_rejects_bad_input(rag_env):
    from rag.retriever import retrieve

    with pytest.raises(ValueError):
        retrieve("   ")
    with pytest.raises(ValueError):
        retrieve("ok", k=0)
