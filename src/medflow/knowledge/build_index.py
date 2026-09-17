"""Chunk the protocol documents and build a persistent Chroma vector index.

Run with:  python -m src.medflow.knowledge.build_index
"""
from __future__ import annotations

import shutil
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from ..config import settings
from ..embeddings import get_embeddings

PROTOCOLS_DIR = Path(__file__).with_name("protocols")
COLLECTION = "protocols"

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


def build(persist_dir: Path | None = None) -> int:
    persist_dir = persist_dir or settings.chroma_path
    if persist_dir.exists():
        shutil.rmtree(persist_dir)
    persist_dir.mkdir(parents=True, exist_ok=True)

    chunks = load_chunks()
    Chroma.from_documents(
        documents=chunks,
        embedding=get_embeddings(),
        collection_name=COLLECTION,
        persist_directory=str(persist_dir),
    )
    print(
        f"Indexed {len(chunks)} chunks from {len(list(PROTOCOLS_DIR.glob('*.md')))} "
        f"protocols into {persist_dir} "
        f"(provider={settings.embeddings_provider})."
    )
    return len(chunks)


def get_vectorstore(persist_dir: Path | None = None) -> Chroma:
    persist_dir = persist_dir or settings.chroma_path
    if not persist_dir.exists():
        raise FileNotFoundError(
            f"Vector index not found at {persist_dir}. Run `make index` "
            "(or `python -m src.medflow.knowledge.build_index`) first."
        )
    return Chroma(
        collection_name=COLLECTION,
        embedding_function=get_embeddings(),
        persist_directory=str(persist_dir),
    )


if __name__ == "__main__":
    build()
