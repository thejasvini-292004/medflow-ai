"""Embeddings factory.

Three providers, selected by `EMBEDDINGS_PROVIDER`:

  * ``openai``  — OpenAIEmbeddings (needs OPENAI_API_KEY). Best quality.
  * ``hf``      — local sentence-transformers (needs optional extra deps).
  * ``hashing`` — a deterministic, dependency-free, offline embedding.

The ``hashing`` provider is the default so the whole project builds and tests
with **no API key and no network** — the way an FDE would validate a pipeline
inside a locked-down client environment before wiring in real embeddings.
It is not semantically strong, but it is stable and good enough for smoke tests
and demos of the plumbing.
"""
from __future__ import annotations

import hashlib
import math
import re

from langchain_core.embeddings import Embeddings

from .config import settings

_TOKEN = re.compile(r"[a-z0-9]+")


class HashingEmbeddings(Embeddings):
    """Deterministic bag-of-words hashed embedding (no deps, no network).

    Each token is hashed into a fixed-size vector via the hashing trick, with
    L2 normalization. Similar texts that share vocabulary get similar vectors.
    """

    def __init__(self, dim: int = 384):
        self.dim = dim

    def _embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for tok in _TOKEN.findall(text.lower()):
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
            idx = h % self.dim
            sign = 1.0 if (h >> 8) % 2 == 0 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


def get_embeddings() -> Embeddings:
    provider = settings.embeddings_provider.lower()

    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(
            model=settings.embeddings_model,
            api_key=settings.openai_api_key or None,
            base_url=settings.llm_base_url or None,
        )

    if provider == "hf":
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
        except ImportError as e:  # pragma: no cover
            raise ImportError(
                "EMBEDDINGS_PROVIDER=hf requires `pip install "
                "langchain-huggingface sentence-transformers`."
            ) from e
        return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

    if provider == "hashing":
        return HashingEmbeddings()

    raise ValueError(f"Unknown EMBEDDINGS_PROVIDER: {settings.embeddings_provider!r}")
