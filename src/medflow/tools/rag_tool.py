"""Protocol retrieval (RAG) tool.

Answers policy / SOP questions ("when do we go on diversion?", "what is the ICU
nurse ratio?", "what's in the readmission bundle?") by retrieving the most
relevant chunks from the protocol vector index and returning them with their
source document, so the agent can cite policy rather than guess.
"""
from __future__ import annotations

from functools import lru_cache

from langchain_core.tools import tool

from ..knowledge.build_index import get_vectorstore


@lru_cache(maxsize=1)
def _retriever():
    return get_vectorstore().as_retriever(search_kwargs={"k": 4})


@tool("search_protocols")
def search_protocols(query: str) -> str:
    """Search the hospital's operational protocols and clinical SOPs (bed
    management, ED triage/diversion, staffing ratios, discharge planning,
    infection control) and return the most relevant policy excerpts with their
    source document. Use this for any 'what is our policy / threshold / target /
    procedure' question, and to interpret what the operational numbers mean.
    """
    docs = _retriever().invoke(query)
    if not docs:
        return "No matching protocol sections were found."
    blocks = []
    for d in docs:
        src = d.metadata.get("source", "unknown")
        section = d.metadata.get("section") or d.metadata.get("policy") or ""
        header = f"[{src}" + (f" — {section}]" if section else "]")
        blocks.append(f"{header}\n{d.page_content.strip()}")
    return "\n\n---\n\n".join(blocks)
