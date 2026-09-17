"""Shared pytest fixtures: build a temp DB + index once per session (offline)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

# Force fully-offline, dependency-light providers for tests.
os.environ.setdefault("EMBEDDINGS_PROVIDER", "hashing")
os.environ.setdefault("SIGNAL_USE_LIVE_API", "false")


@pytest.fixture(scope="session")
def built_db(tmp_path_factory) -> Path:
    from src.medflow.db.generate_data import build

    db_path = tmp_path_factory.mktemp("data") / "test.db"
    build(db_path)
    return db_path


@pytest.fixture(scope="session")
def built_index(tmp_path_factory) -> Path:
    from src.medflow.knowledge.build_index import build

    idx = tmp_path_factory.mktemp("chroma")
    build(idx)
    return idx
