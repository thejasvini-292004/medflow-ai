-- =====================================================================
-- MedFlow AI — operational schema for a mid-size acute-care hospital.
--
-- Design notes (FDE-relevant):
--   * Base tables hold the raw operational records, including a small
--     amount of PII (patient_name) to make the de-identification story real.
--   * The AGENT NEVER SEES THE BASE TABLES. It is given a read-only
--     connection and is instructed to query the `v_*` views only. The
--     views drop PII and expose clean, well-named operational columns.
--   * This mirrors how an FDE would wrap a client's legacy database:
--     least-privilege access + curated views instead of raw tables.
-- =====================================================================

PRAGMA foreign_keys = ON;

-- ---------- Reference: hospital units / wards ----------
DROP TABLE IF EXISTS units;
CREATE TABLE units (
    unit_id        INTEGER PRIMARY KEY,
    unit_code      TEXT NOT NULL UNIQUE,      -- e.g. 'ED', 'ICU', 'MED', 'SURG', 'PEDS', 'OB'
    unit_name      TEXT NOT NULL,
    unit_type      TEXT NOT NULL,             -- 'emergency','critical_care','medical','surgical','pediatric','maternity'
    licensed_beds  INTEGER NOT NULL,
    target_nurse_ratio REAL NOT NULL          -- patients per nurse target for this unit
);

-- ---------- Physical beds ----------
DROP TABLE IF EXISTS beds;
CREATE TABLE beds (
    bed_id      INTEGER PRIMARY KEY,
    unit_id     INTEGER NOT NULL REFERENCES units(unit_id),
    bed_label   TEXT NOT NULL,                -- e.g. 'ICU-04'
    is_isolation INTEGER NOT NULL DEFAULT 0   -- negative-pressure / isolation capable
);

-- ---------- Daily census snapshot per unit ----------
-- One row per unit per day: occupancy + staffing actuals.
DROP TABLE IF EXISTS census_daily;
CREATE TABLE census_daily (
    census_id       INTEGER PRIMARY KEY,
    snapshot_date   TEXT NOT NULL,            -- ISO date
    unit_id         INTEGER NOT NULL REFERENCES units(unit_id),
    occupied_beds   INTEGER NOT NULL,
    staffed_beds    INTEGER NOT NULL,         -- beds actually staffable that day
    nurses_on_shift INTEGER NOT NULL,
    boarders        INTEGER NOT NULL DEFAULT 0 -- admitted patients still physically in the ED
);

-- ---------- Admissions / encounters ----------
DROP TABLE IF EXISTS admissions;
CREATE TABLE admissions (
    admission_id     INTEGER PRIMARY KEY,
    patient_name     TEXT NOT NULL,           -- PII: excluded from all views
    mrn              TEXT NOT NULL,           -- PII: excluded from all views
    age              INTEGER NOT NULL,
    sex              TEXT NOT NULL,
    unit_id          INTEGER NOT NULL REFERENCES units(unit_id),
    admit_ts         TEXT NOT NULL,           -- ISO timestamp
    discharge_ts     TEXT,                    -- null while still admitted
    admit_source     TEXT NOT NULL,           -- 'ED','transfer','elective','direct'
    primary_dx_group TEXT NOT NULL,           -- coarse diagnosis group
    los_hours        REAL,                    -- length of stay (computed at discharge)
    readmit_30d      INTEGER NOT NULL DEFAULT 0,
    payer            TEXT NOT NULL
);

-- ---------- Emergency department visits ----------
DROP TABLE IF EXISTS ed_visits;
CREATE TABLE ed_visits (
    ed_visit_id      INTEGER PRIMARY KEY,
    patient_name     TEXT NOT NULL,           -- PII: excluded from all views
    arrival_ts       TEXT NOT NULL,
    esi_level        INTEGER NOT NULL,        -- Emergency Severity Index 1..5 (1 = most acute)
    chief_complaint  TEXT NOT NULL,
    door_to_provider_min INTEGER NOT NULL,
    ed_los_min       INTEGER NOT NULL,        -- total ED length of stay
    disposition      TEXT NOT NULL,           -- 'admitted','discharged','transferred','lwbs','ama'
    left_without_being_seen INTEGER NOT NULL DEFAULT 0,
    arrival_mode     TEXT NOT NULL            -- 'ambulance','walk_in','police'
);

-- ---------- Staffing roster (per unit per day) ----------
DROP TABLE IF EXISTS staffing;
CREATE TABLE staffing (
    staffing_id     INTEGER PRIMARY KEY,
    shift_date      TEXT NOT NULL,
    unit_id         INTEGER NOT NULL REFERENCES units(unit_id),
    shift           TEXT NOT NULL,            -- 'day','night'
    rns_scheduled   INTEGER NOT NULL,
    rns_actual      INTEGER NOT NULL,
    techs_actual    INTEGER NOT NULL,
    agency_rns      INTEGER NOT NULL DEFAULT 0,
    overtime_hours  REAL NOT NULL DEFAULT 0
);

-- =====================================================================
-- DE-IDENTIFIED READ-ONLY VIEWS  (the agent's ONLY interface)
-- =====================================================================

DROP VIEW IF EXISTS v_units;
CREATE VIEW v_units AS
SELECT unit_id, unit_code, unit_name, unit_type, licensed_beds, target_nurse_ratio
FROM units;

DROP VIEW IF EXISTS v_census_daily;
CREATE VIEW v_census_daily AS
SELECT
    c.snapshot_date,
    u.unit_code,
    u.unit_name,
    c.occupied_beds,
    c.staffed_beds,
    u.licensed_beds,
    ROUND(100.0 * c.occupied_beds / NULLIF(c.staffed_beds, 0), 1) AS occupancy_pct,
    c.nurses_on_shift,
    c.boarders
FROM census_daily c
JOIN units u ON u.unit_id = c.unit_id;

DROP VIEW IF EXISTS v_admissions;
CREATE VIEW v_admissions AS
SELECT
    a.admission_id,
    a.age,
    a.sex,
    u.unit_code,
    u.unit_name,
    a.admit_ts,
    a.discharge_ts,
    a.admit_source,
    a.primary_dx_group,
    a.los_hours,
    a.readmit_30d,
    a.payer
FROM admissions a
JOIN units u ON u.unit_id = a.unit_id;
-- NOTE: patient_name and mrn are intentionally NOT selected here.

DROP VIEW IF EXISTS v_ed_visits;
CREATE VIEW v_ed_visits AS
SELECT
    ed_visit_id,
    arrival_ts,
    esi_level,
    chief_complaint,
    door_to_provider_min,
    ed_los_min,
    disposition,
    left_without_being_seen,
    arrival_mode
FROM ed_visits;
-- NOTE: patient_name intentionally excluded.

DROP VIEW IF EXISTS v_staffing;
CREATE VIEW v_staffing AS
SELECT
    s.shift_date,
    u.unit_code,
    u.unit_name,
    s.shift,
    s.rns_scheduled,
    s.rns_actual,
    s.techs_actual,
    s.agency_rns,
    s.overtime_hours,
    u.target_nurse_ratio
FROM staffing s
JOIN units u ON u.unit_id = s.unit_id;
