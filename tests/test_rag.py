"""The RAG index builds and retrieves relevant protocol chunks."""
from __future__ import annotations

from src.medflow.knowledge.build_index import get_vectorstore


def test_index_retrieves_something(built_index):
    vs = get_vectorstore(built_index)
    docs = vs.similarity_search("nurse to patient ratio in the ICU", k=4)
    assert docs
    sources = {d.metadata.get("source") for d in docs}
    # staffing policy should be among the retrieved sources for a ratio question
    assert "staffing_ratios.md" in sources


def test_diversion_policy_retrievable(built_index):
    vs = get_vectorstore(built_index)
    docs = vs.similarity_search("ambulance diversion criteria", k=4)
    text = " ".join(d.page_content.lower() for d in docs)
    assert "diversion" in text
