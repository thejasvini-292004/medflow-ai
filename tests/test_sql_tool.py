"""The text-to-SQL tool executes valid SELECTs and blocks everything unsafe."""
from __future__ import annotations

import pytest

from src.medflow.db.connection import UnsafeQueryError, assert_safe_select, run_select


def test_valid_select_runs(built_db):
    cols, rows = run_select(
        "SELECT unit_code, AVG(occupancy_pct) AS occ FROM v_census_daily "
        "GROUP BY unit_code",
        db_path=built_db,
    )
    assert "unit_code" in cols
    assert len(rows) == 7


def test_row_cap_applied(built_db):
    _, rows = run_select("SELECT * FROM v_ed_visits", limit=50, db_path=built_db)
    assert len(rows) == 50


@pytest.mark.parametrize(
    "bad",
    [
        "DELETE FROM admissions",
        "UPDATE units SET unit_name='x'",
        "DROP TABLE units",
        "SELECT 1; SELECT 2",
        "INSERT INTO units VALUES (9,'X','x','x',1,1)",
        "SELECT * FROM admissions",       # base table, not the view
        "SELECT patient_name FROM ed_visits",  # base table access
    ],
)
def test_unsafe_queries_blocked(bad):
    with pytest.raises(UnsafeQueryError):
        assert_safe_select(bad)


def test_views_are_allowed():
    # Should not raise.
    assert_safe_select("SELECT * FROM v_admissions")
    assert_safe_select("WITH x AS (SELECT 1 AS a) SELECT a FROM x")
