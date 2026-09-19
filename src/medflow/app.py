"""Streamlit chat UI for MedFlow AI.

Run:  streamlit run src/medflow/app.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# --- Hosted-deployment fix (Streamlit Community Cloud, etc.) ------------------
# Chroma requires sqlite3 >= 3.35, but some hosts ship an older system sqlite3,
# which makes the app crash on import (a blank page). If pysqlite3 is installed
# (it is, on Linux, via requirements.txt) swap it in as the stdlib `sqlite3`
# BEFORE anything imports chromadb. This is a safe no-op locally on macOS.
try:
    __import__("pysqlite3")
    sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
except Exception:  # noqa: BLE001
    pass

# Allow `streamlit run src/medflow/app.py` to import the package.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

# Bridge Streamlit "Secrets" (Cloud) into os.environ so pydantic settings read
# them the same way as a local .env. Safe if no secrets are defined.
try:
    for _k, _v in st.secrets.items():
        os.environ.setdefault(_k, str(_v))
except Exception:  # noqa: BLE001
    pass

from src.medflow.config import settings  # noqa: E402

st.set_page_config(page_title="MedFlow AI", page_icon="🏥", layout="wide")

EXAMPLES = [
    "Which units had the highest average occupancy last winter, and what capacity tier is that?",
    "What was the ED left-without-being-seen rate by month in 2024?",
    "Which diagnosis groups drive the most 30-day readmissions, and what's our reduction bundle?",
    "How often was the ICU night shift understaffed versus our ratio policy?",
    "Given today's environmental signal, should we expect a respiratory surge, and what should we do?",
    "What's the median door-to-provider time for ESI 2 patients, and what's the target?",
]


@st.cache_resource(show_spinner="Preparing hospital data + protocol index (first run only)…")
def _ensure_assets() -> bool:
    """Build the DB and vector index if they're missing.

    On a fresh host (e.g. Streamlit Community Cloud) the generated `data/` folder
    isn't in git, so we build it once on startup instead of requiring a manual
    `make bootstrap`. Cached so it runs a single time per container.
    """
    from src.medflow.db.generate_data import build as build_db
    from src.medflow.knowledge.build_index import build as build_index

    if not settings.db_file.exists():
        build_db()
    if not settings.chroma_path.exists():
        build_index()
    return True


@st.cache_resource(show_spinner="Starting MedFlow agent…")
def _get_agent():
    from src.medflow.agent import build_agent

    return build_agent()


def main() -> None:
    st.title("🏥 MedFlow AI — Patient-Flow Operations Assistant")
    st.caption(
        "Ask about occupancy, ED throughput, staffing, and readmissions. "
        "Answers combine the operational database, hospital protocols, and a live "
        "environmental signal."
    )

    # Build the DB + index on first run if they're missing (fresh host).
    try:
        _ensure_assets()
    except Exception as e:  # noqa: BLE001
        st.error(f"Could not build the data/index on startup: {e}")
        st.stop()

    with st.sidebar:
        st.header("Status")
        st.write(f"**LLM model:** `{settings.llm_model}`")
        st.write(f"**Embeddings:** `{settings.embeddings_provider}`")
        st.write("**LLM key set:** " + ("✅" if settings.has_llm else "❌"))
        st.write("**Database:** " + ("✅" if settings.db_file.exists() else "❌"))
        st.write("**Vector index:** " + ("✅" if settings.chroma_path.exists() else "❌"))
        st.divider()
        st.header("Try asking")
        for q in EXAMPLES:
            if st.button(q, use_container_width=True):
                st.session_state["pending"] = q
        st.divider()
        if st.button("🗑️ Clear conversation", use_container_width=True):
            st.session_state["messages"] = []
            st.rerun()

    if not settings.has_llm:
        st.warning(
            "**No language model configured.** The data and protocol tools are ready, "
            "but answering questions needs an LLM.\n\n"
            "- **On Streamlit Community Cloud:** open the app's **⋮ → Settings → Secrets** "
            "and add `OPENAI_API_KEY = \"sk-...\"` (Ollama can't run on the hosted platform).\n"
            "- **Locally:** set `OPENAI_API_KEY`, or `LLM_BASE_URL` for a local model, in `.env`."
        )
        st.stop()

    if "messages" not in st.session_state:
        st.session_state["messages"] = []  # list of {role, content, trace}

    # Replay history
    for m in st.session_state["messages"]:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
            if m.get("trace"):
                _render_trace(m["trace"])

    prompt = st.chat_input("Ask a patient-flow question…")
    if not prompt and "pending" in st.session_state:
        prompt = st.session_state.pop("pending")

    if prompt:
        st.session_state["messages"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking…"):
                from src.medflow.agent import run_agent

                try:
                    result = run_agent(prompt, agent=_get_agent())
                    answer, trace = result["answer"], result["trace"]
                except Exception as e:  # noqa: BLE001
                    answer, trace = f"⚠️ Error: {e}", []
            st.markdown(answer)
            _render_trace(trace)

        st.session_state["messages"].append(
            {"role": "assistant", "content": answer, "trace": trace}
        )


def _render_trace(trace: list[dict]) -> None:
    if not trace:
        return
    with st.expander(f"🔧 Tools used ({len(trace)})"):
        for i, step in enumerate(trace, 1):
            st.markdown(f"**{i}. `{step['tool']}`**")
            if step.get("input"):
                st.code(str(step["input"]), language="json")
            out = step.get("output", "")
            st.markdown(out if len(out) < 1500 else out[:1500] + " …")


if __name__ == "__main__":
    main()
