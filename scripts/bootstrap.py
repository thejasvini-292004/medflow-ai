"""One-shot setup: build the synthetic database and the protocol vector index.

Run:  python -m scripts.bootstrap
"""
from __future__ import annotations

from src.medflow.db.generate_data import build as build_db
from src.medflow.knowledge.build_index import build as build_index


def main() -> None:
    print("=> Building synthetic hospital database…")
    build_db()
    print("\n=> Building protocol vector index…")
    build_index()
    print("\nDone. Launch the app with:  make app")


if __name__ == "__main__":
    main()
