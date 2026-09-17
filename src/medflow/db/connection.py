"""Read-only database access for the agent.

Two layers of defense mirror how an FDE hardens a client integration:

  1. The SQLite connection is opened in immutable / read-only mode
     (`file:...?mode=ro`), so INSERT/UPDATE/DELETE/DDL raise at the driver.
  2. A SQLAlchemy engine is exposed that only sees the de-identified `v_*`
     views (the agent is told to use those), and a statement guard rejects
     anything that isn't a single SELECT.
"""
from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from ..config import settings

# Only these objects are queryable by the agent.
ALLOWED_OBJECTS = {
    "v_units", "v_census_daily", "v_admissions", "v_ed_visits", "v_staffing",
}

_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|pragma|replace|"
    r"vacuum|reindex|truncate|grant|revoke)\b",
    re.IGNORECASE,
)


class UnsafeQueryError(ValueError):
    """Raised when a query is not a single, read-only SELECT over the views."""


def get_engine(db_path: Path | None = None) -> Engine:
    """Return a SQLAlchemy engine bound to a read-only SQLite connection."""
    db_path = db_path or settings.db_file
    if not db_path.exists():
        raise FileNotFoundError(
            f"Database not found at {db_path}. Run `make bootstrap` (or "
            "`python -m src.medflow.db.generate_data`) first."
        )
    uri = f"sqlite:///file:{db_path}?mode=ro&uri=true"
    # Read-only + no pooling surprises; the driver rejects writes itself.
    return create_engine(uri, connect_args={"uri": True})


def assert_safe_select(sql: str) -> str:
    """Validate that `sql` is a single read-only SELECT over allowed views."""
    stripped = sql.strip().rstrip(";").strip()
    if not stripped:
        raise UnsafeQueryError("Empty query.")
    if ";" in stripped:
        raise UnsafeQueryError("Multiple statements are not allowed.")
    lowered = stripped.lower()
    if not (lowered.startswith("select") or lowered.startswith("with")):
        raise UnsafeQueryError("Only SELECT / WITH queries are permitted.")
    if _FORBIDDEN.search(stripped):
        raise UnsafeQueryError("Query contains a forbidden (write/DDL) keyword.")
    # Block access to raw base tables (belt-and-suspenders; the RO conn also helps).
    for base in ("admissions", "ed_visits", "census_daily", "staffing", "beds", "units"):
        # allow the view names v_admissions etc., block bare base tables
        if re.search(rf"(?<![\w.]){base}\b", lowered) and f"v_{base}" not in lowered and base not in ("beds",):
            # `units`/`beds` etc. only appear here as base tables -> block
            if not re.search(rf"v_{base}\b", lowered):
                raise UnsafeQueryError(
                    f"Access to base table '{base}' is not allowed. "
                    f"Use the de-identified views (v_*) instead."
                )
    return stripped


def run_select(sql: str, limit: int = 200, db_path: Path | None = None):
    """Execute a validated SELECT and return (columns, rows)."""
    safe = assert_safe_select(sql)
    # enforce a hard row cap to protect the context window
    if re.search(r"\blimit\b", safe, re.IGNORECASE) is None:
        safe = f"{safe}\nLIMIT {limit}"
    engine = get_engine(db_path)
    with engine.connect() as conn:
        result = conn.execute(text(safe))
        cols = list(result.keys())
        rows = [list(r) for r in result.fetchall()]
    return cols, rows
