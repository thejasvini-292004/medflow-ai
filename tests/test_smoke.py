"""Import-level smoke tests + tool wiring that need no API key or network."""
from __future__ import annotations

import pytest


def test_tools_registered():
    from src.medflow.agent import TOOLS

    names = {t.name for t in TOOLS}
    assert names == {"query_hospital_db", "search_protocols", "get_environmental_signal"}


def test_system_prompt_present():
    from src.medflow.agent import SYSTEM_PROMPT

    assert "MedFlow AI" in SYSTEM_PROMPT
    assert len(SYSTEM_PROMPT) > 200


def test_signal_offline_fallback():
    from src.medflow.tools.signals_tool import get_environmental_signal

    out = get_environmental_signal.invoke({})
    assert any(band in out for band in ("LOW", "ELEVATED", "HIGH"))


def test_build_agent_requires_llm(monkeypatch):
    # With no LLM configured, build_agent should fail loudly (not silently).
    from src.medflow import agent, config

    monkeypatch.setattr(config.settings, "openai_api_key", "", raising=False)
    monkeypatch.setattr(config.settings, "llm_base_url", "", raising=False)
    with pytest.raises(RuntimeError):
        agent.build_agent()


def test_app_module_imports():
    # Ensures the Streamlit module has no import-time syntax/wiring errors.
    import importlib

    importlib.import_module("src.medflow.app")
