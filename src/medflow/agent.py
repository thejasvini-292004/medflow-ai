"""LangGraph ReAct agent that orchestrates the three MedFlow tools.

The agent decides, per question, whether to (a) query the operational database,
(b) look up a protocol/policy, (c) check the external environmental signal, or
some combination — then reasons over the results and answers, citing the policy
documents and noting the numbers it used.
"""
from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.prebuilt import create_react_agent

from .config import settings
from .tools.rag_tool import search_protocols
from .tools.signals_tool import get_environmental_signal
from .tools.sql_tool import query_hospital_db

TOOLS = [query_hospital_db, search_protocols, get_environmental_signal]

SYSTEM_PROMPT = """
You are **MedFlow AI**, an operations analyst assistant for a mid-size acute-care
hospital. You help charge nurses, house supervisors, and administrators
understand patient flow, capacity, staffing, ED throughput, and readmissions.

You have three tools:
1. `query_hospital_db` — run read-only SQL over de-identified operational views
   to get the actual numbers. Prefer this for anything quantitative
   (occupancy, boarders, LOS, ED wait times, readmission counts, staffing).
2. `search_protocols` — retrieve the hospital's own policies/SOPs (capacity
   escalation tiers, ED diversion criteria, nurse ratios, discharge/readmission
   bundle, infection-control surge rules). Use it to interpret numbers against
   thresholds and to answer "what is our policy/target" questions.
3. `get_environmental_signal` — current weather + a respiratory-surge proxy, for
   questions about expected patient influx or capacity planning ahead.

How to work:
- Think about which tools are needed. Many good answers combine the database
  (what is happening) with a protocol (what the threshold/policy is), e.g.
  "MED is at 101% occupancy — that is RED under OPS-BED-001, which calls for ...".
- Write correct SQLite against the v_* views only; never invent columns. If a
  query errors, read the message and retry with a corrected query.
- Be concise and operational. Lead with the answer, then the evidence.
- Cite protocols by their document/ID when you rely on them.
- Never claim access to patient identities — the data is de-identified by design.
- If the data cannot answer the question, say so plainly rather than guessing.
""".strip()


def build_llm():
    """Construct the chat model from settings (any OpenAI-compatible endpoint)."""
    if not settings.has_llm:
        raise RuntimeError(
            "No LLM configured. Set OPENAI_API_KEY (and optionally LLM_BASE_URL "
            "for a local/compatible endpoint) in your .env."
        )
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        api_key=settings.openai_api_key or "not-needed",
        base_url=settings.llm_base_url or None,
    )


def build_agent(llm: Any | None = None):
    """Return a compiled LangGraph ReAct agent."""
    llm = llm or build_llm()
    return create_react_agent(llm, TOOLS, prompt=SYSTEM_PROMPT)


def _tool_trace(messages: list) -> list[dict]:
    """Extract a compact (tool, input, output) trace for display."""
    trace: list[dict] = []
    pending: dict[str, dict] = {}
    for m in messages:
        if isinstance(m, AIMessage):
            for call in m.tool_calls or []:
                pending[call["id"]] = {"tool": call["name"], "input": call["args"]}
        elif isinstance(m, ToolMessage):
            entry = pending.pop(m.tool_call_id, {"tool": m.name, "input": None})
            entry["output"] = m.content
            trace.append(entry)
    return trace


def run_agent(question: str, history: list | None = None, agent=None) -> dict:
    """Run one turn and return {'answer', 'trace', 'messages'}.

    `history` is an optional list of prior LangChain messages for multi-turn chat.
    """
    agent = agent or build_agent()
    msgs: list = [SystemMessage(content=SYSTEM_PROMPT)] if not history else list(history)
    msgs.append(HumanMessage(content=question))
    result = agent.invoke({"messages": msgs})
    out_messages = result["messages"]
    answer = out_messages[-1].content
    return {
        "answer": answer,
        "trace": _tool_trace(out_messages),
        "messages": out_messages,
    }
