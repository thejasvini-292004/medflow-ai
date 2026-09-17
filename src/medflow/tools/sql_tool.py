"""Text-to-SQL tool.

The LLM writes SQLite SELECT statements against a small set of de-identified
views. This tool validates the statement (read-only, single SELECT, views only)
and returns the results as a compact markdown table. The view schema is embedded
in the tool description so the model knows exactly what columns exist.
"""
from __future__ import annotations

from langchain_core.tools import tool

from ..db.connection import UnsafeQueryError, run_select

SCHEMA_DOC = """
You may ONLY query these read-only, de-identified SQLite VIEWS (never base tables):

v_units(unit_id, unit_code, unit_name, unit_type, licensed_beds, target_nurse_ratio)
  - unit_code in ('ED','ICU','MED','SURG','PEDS','OB','OBS')
  - target_nurse_ratio = target patients per nurse for the unit.

v_census_daily(snapshot_date, unit_code, unit_name, occupied_beds, staffed_beds,
               licensed_beds, occupancy_pct, nurses_on_shift, boarders)
  - one row per unit per day. occupancy_pct = 100*occupied/staffed.
  - boarders = admitted patients still held in the ED (ED/MED/ICU rows).

v_admissions(admission_id, age, sex, unit_code, unit_name, admit_ts, discharge_ts,
             admit_source, primary_dx_group, los_hours, readmit_30d, payer)
  - admit_source in ('ED','elective','transfer','direct')
  - primary_dx_group e.g. 'heart_failure','copd','pneumonia','sepsis','stroke',...
  - readmit_30d is 1 if readmitted within 30 days. discharge_ts is NULL if still admitted.
  - los_hours is length of stay in hours (NULL while admitted).

v_ed_visits(ed_visit_id, arrival_ts, esi_level, chief_complaint,
            door_to_provider_min, ed_los_min, disposition,
            left_without_being_seen, arrival_mode)
  - esi_level 1..5 (1 = most acute). disposition in
    ('admitted','discharged','transferred','lwbs','ama').

v_staffing(shift_date, unit_code, unit_name, shift, rns_scheduled, rns_actual,
           techs_actual, agency_rns, overtime_hours, target_nurse_ratio)
  - shift in ('day','night'). rns_actual already includes agency_rns.

Dates are ISO strings ('YYYY-MM-DD'); timestamps are 'YYYY-MM-DDTHH:MM'.
Use date(column) or substr(column,1,7) for month grouping. Always add
appropriate GROUP BY / ORDER BY and a LIMIT for row-returning queries.
""".strip()


def _to_markdown(cols: list[str], rows: list[list]) -> str:
    if not rows:
        return "(no rows)"
    head = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    body = "\n".join(
        "| " + " | ".join("" if v is None else str(v) for v in r) + " |" for r in rows
    )
    return "\n".join([head, sep, body])


@tool("query_hospital_db", parse_docstring=False)
def query_hospital_db(sql: str) -> str:
    """Run a single read-only SQLite SELECT against the hospital operational views
    and return the result as a markdown table.

    Input MUST be one valid SQLite SELECT (or WITH ... SELECT) statement that
    references only the v_* views described in the tool schema. Writes, DDL,
    multiple statements, and base-table access are rejected. Results are capped
    at 200 rows.
    """
    try:
        cols, rows = run_select(sql, limit=200)
    except UnsafeQueryError as e:
        return f"REJECTED (unsafe query): {e}. Only read-only SELECTs over v_* views are allowed."
    except Exception as e:  # noqa: BLE001 - surface DB errors back to the model
        return f"SQL ERROR: {e}. Check column/view names against the schema and retry."
    table = _to_markdown(cols, rows)
    note = f"\n\n({len(rows)} row(s) returned; capped at 200.)" if len(rows) >= 200 else ""
    return table + note


# Attach schema to the tool description so the agent sees it in the prompt.
query_hospital_db.description = (
    query_hospital_db.description + "\n\n" + SCHEMA_DOC
)
