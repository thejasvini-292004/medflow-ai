# MedFlow AI — Architecture & End-to-End Walkthrough

This document explains the whole project the way a Forward Deployed Engineer would hand it
off: what problem it solves, why each piece exists, how the pieces fit together, how it was
verified, and how you would take it to production. It also maps every part back to the
original FDE reference project (Krish Naik's cold-chain logistics assistant) so you can see
what was kept, what was changed, and why.

---

## 1. What an "AI FDE project" actually is

A Forward Deployed Engineer embeds with a client, learns their messy real-world systems, and
ships a working AI solution on top of them. The recurring pattern for these projects is
almost always the same three-part shape:

1. **Structured data the client already has** — usually a legacy relational database that
   business users can't query without a BI team. The AI turns natural language into SQL.
2. **Unstructured knowledge the client already has** — policies, SOPs, compliance manuals,
   contracts. The AI retrieves and reasons over these with RAG.
3. **An external signal** — a live API (weather, market data, traffic, public-health feeds)
   that adds context the internal data doesn't capture.

An agent stitches these together, a UI makes it usable, and Docker/CI/cloud makes it
shippable. MedFlow AI is that exact shape, applied to **hospital patient-flow operations**.

### The client scenario

*MedFlow General is a mid-size acute-care hospital. Charge nurses and house supervisors make
capacity decisions all day — when to open overflow beds, when the ED is heading for
diversion, whether a unit is understaffed against ratio, which discharges to prioritize. The
data exists (an operational database) and the rules exist (a binder of protocols), but nobody
can cross-reference them in real time. They want to ask questions in plain English and get an
answer that combines the live numbers with the actual policy.*

That framing drives every design choice below.

---

## 2. The four layers

### 2.1 Data layer — the operational database

`src/medflow/db/` builds a synthetic but realistic SQLite database (`make bootstrap`) of a
hospital's operations spanning 2023–2024: **~64,000 records** across units, beds, a daily
census, admissions, ED visits, and staffing rosters.

The data is generated with a fixed seed (`generate_data.py`) and deliberately contains
*discoverable structure* — the kinds of patterns an operations analyst (or the agent) should
be able to surface:

- a **winter respiratory surge** (Nov–Feb, peaking in January) that lifts ED volume and
  drives MED/ICU/PEDS occupancy over 100% with ED boarding;
- a **weekend drop-off** in elective surgical admissions;
- **chronic night-shift understaffing** in MED and ICU relative to the ratio policy;
- a **readmission signal** concentrated in heart-failure and COPD patients.

These aren't cosmetic — they're what make demo questions produce meaningful answers, and what
the test suite asserts on (e.g. January MED occupancy > July; HF/COPD readmission rate >
baseline).

#### The security model (this is the FDE part)

In a real hospital, this data is PHI. So access is hardened in two layers, exactly as you'd
harden a client integration:

1. **De-identified views.** The base tables (`admissions`, `ed_visits`) hold `patient_name`
   and `mrn`. The agent never sees them. It is only ever pointed at the `v_*` views defined in
   `schema.sql`, which drop the PII columns and expose clean, well-named operational fields.
   *De-identification happens in the data layer, not in a prompt instruction the model might
   ignore.*
2. **Read-only + statement guard.** `connection.py` opens SQLite in read-only mode
   (`file:...?mode=ro`) so the driver itself rejects writes, and `assert_safe_select()`
   independently rejects anything that isn't a single `SELECT`/`WITH`, blocks write/DDL
   keywords, blocks stacked statements, and blocks references to the raw base tables. A hard
   `LIMIT` is injected to protect the context window.

This is belt-and-suspenders on purpose: least-privilege credentials *and* curated views *and*
an application-level allow-list. The test suite proves each guard fires
(`tests/test_sql_tool.py`).

### 2.2 Knowledge layer — protocols + RAG

`src/medflow/knowledge/protocols/` contains five markdown SOPs written to read like real
hospital policy: bed-management capacity tiers (GREEN/YELLOW/ORANGE/RED), ED triage &
diversion criteria, nurse staffing ratios, discharge planning & readmission reduction, and
infection-control / respiratory-surge rules. Crucially, they contain **specific thresholds**
(e.g. "RED = staffed occupancy > 97% or ED boarders ≥ 15") so the agent can turn a raw number
into an operational judgment.

`build_index.py` chunks these on markdown headers, then into ~800-character overlapping
windows, embeds them, and persists them to a **Chroma** vector store. `rag_tool.py` exposes a
retriever the agent calls to fetch the relevant policy excerpts *with their source document*,
so answers can cite `OPS-BED-001` rather than hallucinate a threshold.

#### Embeddings: the offline-first choice

`embeddings.py` is a factory with three providers: `openai` (best quality), `hf` (local
sentence-transformers), and `hashing`. The `hashing` provider is a dependency-free,
network-free, deterministic embedding (the hashing trick + L2 normalization). It's the
default so the **entire project builds, indexes, and tests with no API key and no internet** —
the reality of validating a pipeline inside a locked-down client environment before you're
allowed to wire in a hosted embedding service. You flip one env var (`EMBEDDINGS_PROVIDER`)
and rerun `make index` to upgrade retrieval quality for production.

### 2.3 External-signal layer

`signals_tool.py` calls **Open-Meteo** (a free, keyless weather API) for the hospital's region
and derives a **respiratory-illness surge proxy** from the season and temperature — a genuine
real-world driver of ED respiratory volume. If the network is unavailable or the live API is
disabled, it falls back to a deterministic seasonal estimate so the tool *always* returns
something usable. That graceful degradation is another FDE habit: never let one flaky external
dependency take down the assistant.

### 2.4 Orchestration + presentation

`agent.py` assembles a **LangGraph ReAct agent** (`create_react_agent`) over the three tools
with a system prompt that tells it how to behave: prefer the database for numbers, use
protocols to interpret them against thresholds, cite policies, never claim access to patient
identities, and retry a corrected query if SQL errors. The LLM is any OpenAI-compatible chat
model (`build_llm()` reads model/base-URL/key from settings), so you can run GPT-4o-mini, a
local Ollama model, or an enterprise endpoint without code changes.

`app.py` is a **Streamlit** chat UI with session state, clickable example questions, a
live setup-status sidebar, and an expandable **"tools used" trace** so users can see exactly
which SQL ran and which protocol was retrieved — transparency that builds trust with
operational staff.

---

## 3. How a question flows through the system

Take *"Which units were most crowded last winter and what capacity tier is that?"*

1. The user's message enters the LangGraph agent with the system prompt.
2. The LLM decides it needs numbers and emits a tool call to `query_hospital_db` with a
   `SELECT` grouping `v_census_daily` by unit for the winter months.
3. The safety guard validates the SQL, the read-only connection runs it, and a markdown table
   of average occupancy per unit comes back.
4. The LLM sees MED/OBS/ICU near or above 100% and calls `search_protocols` for the capacity
   escalation policy.
5. The retriever returns the OPS-BED-001 tier definitions.
6. The LLM synthesizes: *"MED and OBS ran at ~101% staffed occupancy in January — that's the
   RED tier under OPS-BED-001, which calls for diversion review, holding elective admissions,
   and 2-hour bed huddles."* The UI shows the answer plus the two-step tool trace.

This is the ReAct loop: **reason → act (tool) → observe → repeat → answer.**

---

## 4. How it was verified

Because a live LLM needs a key, verification is split:

- **Deterministic pipeline** (data, security guards, RAG, tools, wiring) is covered by 21
  offline `pytest` tests that build a temp DB and index with the hashing embeddings.
- **The full ReAct loop** was exercised with a *scripted* chat model that stands in for the
  LLM: it deterministically calls `query_hospital_db`, then `search_protocols`, then produces
  a final answer from the tool outputs. This proves the LangGraph orchestration, tool
  execution, and trace extraction all work end-to-end; only the model's token generation is
  mocked. With a real key set, the same `run_agent()` path drives a real LLM unchanged.
- **CI** (`.github/workflows/ci.yml`) runs `ruff` lint + the test suite fully offline, then
  builds the Docker image.

---

## 5. Taking it to production

The repo ships a `Dockerfile` (builds the DB + index into the image so the container is
self-contained) and `docker-compose.yml`. To mirror the original project's AWS EC2 deployment:

1. Push the image to a registry (ECR).
2. Run it on an EC2 instance (or ECS/Fargate) with the security group exposing only port 8501
   behind an ALB, and inject secrets (`OPENAI_API_KEY`) via the environment or Secrets
   Manager rather than baking them in.
3. Point the app at the client's real database by replacing `connection.py`'s engine URL with
   the production DSN — keeping the read-only user + views contract — and swap
   `EMBEDDINGS_PROVIDER` to `openai`/`hf`.
4. Add a GitHub Actions deploy job (build → push to ECR → update the service) after the
   existing test/lint/build stages.

For a real hospital you'd also add: LangSmith tracing (hooks are already stubbed in
`.env.example`), authentication in front of Streamlit, per-user audit logging of every SQL the
agent runs, and a human-review step before any operational action.

---

## 6. Mapping to the original FDE reference project

| Concern | Original (cold-chain logistics) | MedFlow AI (this project) |
|--------|--------------------------------|---------------------------|
| Domain | Supply-chain / cold-chain ops | Hospital patient flow |
| Structured DB | MSSQL Server 2022 | SQLite (portable, zero-setup) |
| Text-to-SQL | LangChain SQL agent | LangGraph ReAct + guarded SQL tool |
| Vector DB / RAG | Pinecone (compliance docs) | Chroma (hospital protocols) |
| Embeddings | OpenAI | Factory: openai / hf / offline-hashing |
| External tool | Weather API | Open-Meteo + respiratory-surge proxy (with fallback) |
| Security | Read-only DB user + views | Read-only conn + de-identified views + SQL guard |
| UI | Streamlit | Streamlit (+ tool-trace viewer) |
| Packaging | Docker | Docker + docker-compose |
| Deploy | AWS EC2 + GitHub Actions | Docker image + CI; EC2/ECS notes above |
| Runs offline? | No (needs cloud accounts) | Yes (full pipeline + tests, no keys) |

Same architecture, different domain, distinct code — and engineered to run and be tested
anywhere, which is exactly what you want when demoing an FDE build to a new client.
