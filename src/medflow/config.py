"""Central configuration, loaded from environment / .env.

Every setting has a default so the project imports and runs without a .env file.
Secrets (API keys) default to empty and are only required for the live LLM path.
"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repository root = three levels up from this file (src/medflow/config.py)
ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- LLM ---
    openai_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str = ""  # blank => default OpenAI endpoint
    llm_temperature: float = 0.0

    # --- Embeddings ---
    embeddings_provider: str = "hashing"  # openai | hf | hashing
    embeddings_model: str = "text-embedding-3-small"

    # --- Paths (resolved relative to repo root if not absolute) ---
    db_path: str = "data/medflow.db"
    index_path: str = "data/protocol_index.json"

    # --- External signal tool ---
    signal_lat: float = 34.0522
    signal_lon: float = -118.2437
    signal_use_live_api: bool = True

    @property
    def db_file(self) -> Path:
        p = Path(self.db_path)
        return p if p.is_absolute() else ROOT_DIR / p

    @property
    def index_file(self) -> Path:
        p = Path(self.index_path)
        return p if p.is_absolute() else ROOT_DIR / p

    @property
    def has_llm(self) -> bool:
        """True when an LLM call can plausibly be made."""
        return bool(self.openai_api_key) or bool(self.llm_base_url)


settings = Settings()
