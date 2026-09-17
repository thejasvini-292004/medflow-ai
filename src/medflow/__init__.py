"""MedFlow AI — a hospital patient-flow operations assistant.

An FDE-style reference project: a LangGraph agent that answers natural-language
questions about hospital operations by combining three tools:

  1. text-to-SQL over a de-identified operational database (SQLite),
  2. retrieval over clinical / operational protocols (Chroma RAG), and
  3. a live environmental-signal tool (weather / respiratory-illness proxy).
"""

__version__ = "0.1.0"
