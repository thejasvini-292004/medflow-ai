"""The synthetic dataset is well-formed and has the structure we designed in."""
from __future__ import annotations

import sqlite3


def _q(db, sql):
    con = sqlite3.connect(db)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def test_row_counts(built_db):
    counts = {
        t: _q(built_db, f"SELECT COUNT(*) FROM {t}")[0][0]
        for t in ("units", "beds", "census_daily", "admissions", "ed_visits", "staffing")
    }
    assert counts["units"] == 7
    assert counts["census_daily"] == 7 * 731  # 7 units x 2 years of days
    assert counts["staffing"] == counts["census_daily"] * 2  # day + night
    assert counts["ed_visits"] > 20000
    assert sum(counts.values()) > 40000


def test_views_are_deidentified(built_db):
    # v_admissions / v_ed_visits must NOT expose PII columns.
    cols_adm = [r[1] for r in _q(built_db, "PRAGMA table_info(v_admissions)")]
    cols_ed = [r[1] for r in _q(built_db, "PRAGMA table_info(v_ed_visits)")]
    for banned in ("patient_name", "mrn"):
        assert banned not in cols_adm
        assert banned not in cols_ed


def test_winter_surge_signal(built_db):
    # Medical occupancy should be materially higher in Jan than in Jul.
    jan = _q(
        built_db,
        "SELECT AVG(occupancy_pct) FROM v_census_daily "
        "WHERE unit_code='MED' AND substr(snapshot_date,6,2)='01'",
    )[0][0]
    jul = _q(
        built_db,
        "SELECT AVG(occupancy_pct) FROM v_census_daily "
        "WHERE unit_code='MED' AND substr(snapshot_date,6,2)='07'",
    )[0][0]
    assert jan > jul


def test_readmissions_concentrated_in_hf_copd(built_db):
    rate = dict(
        _q(
            built_db,
            "SELECT primary_dx_group, AVG(readmit_30d) FROM v_admissions "
            "GROUP BY primary_dx_group",
        )
    )
    baseline = rate["pneumonia"]
    assert rate["heart_failure"] > baseline
    assert rate["copd"] > baseline
