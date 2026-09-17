# 🏥 MedFlow AI — Hospital Patient-Flow Operations Assistant

An end-to-end **AI Forward Deployed Engineer (FDE)** reference project: a natural-language
assistant that lets hospital operations staff ask questions about patient flow and get
answers grounded in **real operational data**, the hospital's **own protocols**, and a
**live external signal** — instead of hunting through dashboards.

> Ask *"Which units were most crowded last winter and what capacity tier is that?"* and the
> agent queries the operations database, looks up the escalation policy, and answers with the
> numbers **and** the matching protocol threshold.

This project mirrors the architecture of a classic FDE build (a text-to-SQL agent over a
legacy database + a RAG tool over compliance documents + an external API tool, wrapped in a
UI and shipped with Docker/CI) but in a **different domain** (hospital operations, not cold-chain
logistics) with a **fully local, runnable stack** — no cloud accounts required to try it.

---

## What it does

MedFlow AI is a **LangGraph ReAct agent** with three tools:

| Tool | What it does | Backed by |
|------|--------------|-----------|
| `query_hospital_db` | Writes & runs read-only SQL to get the actual numbers (occupancy, ED wait times, staffing, readmissions) | SQLite + de-identified views |
| `search_protocols` | Retrieves the hospital's policies/SOPs to interpret those numbers against thresholds | Chroma vector store (RAG) |
| `get_environmental_signal` | Pulls current weather + a respiratory-surge proxy for capacity planning | Open-Meteo API (+ offline fallback) |

The agent decides which tools to use per question and combines them — e.g. *"MED ran at 101%
occupancy in January (data), which is **RED** under OPS-BED-001 (protocol), so diversion review
and elective-admission holds apply."*

---

## Architecture

```
                         ┌──────────────────────────────┐
                         │        Streamlit UI          │  presentation
                         │   chat + tool-trace viewer   │
                         └───────────────┬──────────────┘
                                         │
                         ┌───────────────▼───────────────┐
                         │      LangGraph ReAct Agent    │ orchestration
                         │  (LLM plans → calls tools →   │
                         │   reasons → answers, cites)   │
                         └───┬───────────┬───────────────┘
                             │           │           │
              ┌──────────────▼──┐  ┌─────▼──────┐  ┌─▼────────────────┐
              │ query_hospital_ │  │  search_   │  │ get_environmental│  tools
              │ db (text-to-SQL)│  │  protocols │  │ _signal          │
              └────────┬────────┘  └─────┬──────┘  └────────┬─────────┘
                       │                 │                  │
             ┌─────────▼────────┐ ┌──────▼───────┐   ┌──────▼───────┐
             │ SQLite (RO conn, │ │  Chroma      │   │ Open-Meteo   │  data
             │ de-id v_* views) │ │  (protocol   │   │ (+ offline   │
             │  64k+ records    │ │   embeddings)│   │  fallback)   │
             └──────────────────┘ └──────────────┘   └──────────────┘
```

Security is treated the way an FDE would harden a client integration: the agent gets a
**read-only** SQLite connection, may query **only de-identified `v_*` views** (patient names
and MRNs never leave the base tables), and a statement guard rejects anything that isn't a
single `SELECT`. See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full design write-up and how
it maps to the original FDE reference project.

---

## Quickstart

```bash
# 1. Install
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Build the synthetic database + protocol vector index
make bootstrap          # or: python -m scripts.bootstrap

# 3. Configure (copy the template; defaults already work offline)
cp .env.example .env
#    -> set OPENAI_API_KEY to enable the chat assistant
#    -> or point LLM_BASE_URL at a local Ollama/vLLM endpoint

# 4. Run
make app                # streamlit run src/medflow/app.py
```

Open http://localhost:8501 and click one of the example questions.

### Run with Docker

```bash
make docker-build
make docker-run         # serves on http://localhost:8501, reads .env
# or: docker compose up --build
```

---

## Configuration

Everything is set via `.env` (see `.env.example`). Highlights:

- **LLM** — `OPENAI_API_KEY` + `LLM_MODEL` (default `gpt-4o-mini`). Point `LLM_BASE_URL` at any
  OpenAI-compatible endpoint (Ollama, vLLM, Azure, Together, …) to run a local/other model.
- **Embeddings** — `EMBEDDINGS_PROVIDER = hashing | openai | hf`.
  `hashing` (default) is deterministic, needs **no key and no network** — ideal for CI,
  offline demos, or locked-down client environments. Switch to `openai` (or `hf` for local
  sentence-transformers) for production-quality retrieval, then rerun `make index`.
- **External signal** — `SIGNAL_LAT`/`SIGNAL_LON` set the region; `SIGNAL_USE_LIVE_API=false`
  forces the deterministic seasonal fallback.

The app runs with **no API key at all** except that the chat answers need an LLM; the data
pipeline, RAG index, tools, and full test suite all run completely offline.

---

## Testing

```bash
make test        # pytest -q  (21 tests, fully offline)
```

The suite verifies the synthetic data structure and de-identification, the read-only SQL
guard (writes / base-table access / stacked statements are all blocked), RAG retrieval, and
agent/tool wiring. CI (GitHub Actions) additionally lints with `ruff` and builds the Docker
image. See [`ARCHITECTURE.md`](ARCHITECTURE.md) for how the end-to-end ReAct loop is verified
without a live LLM.

---

## Project layout

```
medflow-ai/
├── src/medflow/
│   ├── config.py              # env-driven settings
│   ├── embeddings.py          # openai | hf | offline-hashing factory
│   ├── agent.py               # LangGraph ReAct agent + system prompt
│   ├── app.py                 # Streamlit chat UI
│   ├── db/
│   │   ├── schema.sql         # tables + de-identified v_* views
│   │   ├── generate_data.py   # synthetic hospital data generator (seeded)
│   │   └── connection.py      # read-only connection + SQL safety guard
│   ├── knowledge/
│   │   ├── protocols/*.md      # the hospital's SOPs (RAG corpus)
│   │   └── build_index.py     # chunk + embed -> Chroma
│   └── tools/
│       ├── sql_tool.py        # text-to-SQL tool
│       ├── rag_tool.py        # protocol retrieval tool
│       └── signals_tool.py    # weather / respiratory-surge tool
├── scripts/bootstrap.py       # build DB + index in one shot
├── tests/                     # pytest suite (offline)
├── Dockerfile / docker-compose.yml
└── .github/workflows/ci.yml
```

---

## How this differs from the original FDE project

The video builds a **cold-chain logistics** assistant on **MSSQL + Pinecone + OpenAI**,
deployed to **AWS EC2**. MedFlow keeps the same *shape* (SQL agent + RAG + external tool +
Streamlit + Docker + CI) but is a distinct build:

- **Domain:** hospital patient flow, with its own schema, protocols, and metrics.
- **Stack:** SQLite + Chroma so it runs anywhere with zero cloud setup.
- **Portability:** provider-agnostic LLM/embeddings, incl. a fully offline mode.
- **Security angle:** HIPAA-style de-identification via read-only views, not just RO creds.
- **Resilience:** the external tool degrades gracefully to a deterministic fallback.

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full comparison and a walkthrough of every
component and the design decisions behind it.

---

*Synthetic data only — no real patients. This is an educational reference project.*
