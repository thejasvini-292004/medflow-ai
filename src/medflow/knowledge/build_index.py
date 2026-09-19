"""Chunk the protocol documents and build a lightweight, persistent vector index.

Uses LangChain's dependency-free ``InMemoryVectorStore`` (pure Python, persisted
to a small JSON file). For a corpus this size (a handful of SOPs, ~25 chunks)
this is faster to load, uses a fraction of the memory, and needs no native
libraries or a modern system ``sqlite3`` — which makes it deploy cleanly on
constrained hosts like Streamlit Community Cloud.

Run with:  python -m src.medflow.knowledge.build_index
"""
from __future__ import annotations

from pathlib import Path

from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from ..config import settings
from ..embeddings import get_embeddings

PROTOCOLS_DIR = Path(__file__).with_name("protocols")

_HEADERS = [("#", "policy"), ("##", "section")]


def load_chunks() -> list[Document]:
    """Split each protocol on markdown headers, then into ~800-char windows."""
    header_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=_HEADERS)
    char_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)

    docs: list[Document] = []
    for md_path in sorted(PROTOCOLS_DIR.glob("*.md")):
        text = md_path.read_text()
        for sec in header_splitter.split_text(text):
            for piece in char_splitter.split_documents([sec]):
                piece.metadata["source"] = md_path.name
                docs.append(piece)
    return docs


def build(index_file: Path | None = None) -> int:
    index_file = index_file or settings.index_file
    index_file.parent.mkdir(parents=True, exist_ok=True)

    chunks = load_chunks()
    store = InMemoryVectorStore(embedding=get_embeddings())
    store.add_documents(chunks)
    store.dump(str(index_file))
    print(
        f"Indexed {len(chunks)} chunks from {len(list(PROTOCOLS_DIR.glob('*.md')))} "
        f"protocols into {index_file} (provider={settings.embeddings_provider})."
    )
    return len(chunks)


def get_vectorstore(index_file: Path | None = None) -> InMemoryVectorStore:
    index_file = index_file or settings.index_file
    if not index_file.exists():
        raise FileNotFoundError(
            f"Vector index not found at {index_file}. Run `make index` "
            "(or `python -m src.medflow.knowledge.build_index`) first."
        )
    return InMemoryVectorStore.load(str(index_file), get_embeddings())


if __name__ == "__main__":
    build()
