"""Generate a realistic-but-synthetic hospital operations database (SQLite).

Everything is fabricated with a fixed random seed so the dataset is
reproducible. The data has deliberate structure an analyst (or agent) can
discover:

  * a winter respiratory surge (Nov-Feb) that lifts ED volume and MED/PEDS/ICU
    occupancy and boarding,
  * weekend elective-surgery drop-off,
  * chronic night-shift understaffing in a couple of units,
  * a readmission signal concentrated in heart-failure / COPD groups.

Run with:  python -m src.medflow.db.generate_data
"""
from __future__ import annotations

import math
import random
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from ..config import settings

SEED = 42
START_DATE = date(2023, 1, 1)
END_DATE = date(2024, 12, 31)

SCHEMA_PATH = Path(__file__).with_name("schema.sql")

# unit_code, name, type, licensed_beds, target_nurse_ratio (patients per nurse)
UNITS = [
    ("ED", "Emergency Department", "emergency", 40, 4.0),
    ("ICU", "Intensive Care Unit", "critical_care", 24, 2.0),
    ("MED", "Medical / Telemetry", "medical", 64, 5.0),
    ("SURG", "Surgical", "surgical", 48, 5.0),
    ("PEDS", "Pediatrics", "pediatric", 28, 4.0),
    ("OB", "Labor & Delivery", "maternity", 20, 3.0),
    ("OBS", "Observation / Short Stay", "medical", 26, 5.0),
]

FIRST_NAMES = "James Mary John Patricia Robert Jennifer Michael Linda David Elizabeth Maria Jose Wei Mei Ahmed Fatima Sofia Liam Olivia Noah Emma Aiden Chloe Diego Ana".split()
LAST_NAMES = "Smith Johnson Williams Brown Jones Garcia Miller Davis Rodriguez Martinez Hernandez Lopez Gonzalez Wilson Anderson Nguyen Kim Patel Chen Khan Rossi Silva Cohen Reyes Ali".split()

DX_GROUPS = [
    "heart_failure", "copd", "pneumonia", "sepsis", "chest_pain",
    "stroke", "diabetes", "trauma_ortho", "gi_bleed", "cellulitis",
    "uti", "asthma", "childbirth", "post_surgical", "renal",
]
CHIEF_COMPLAINTS = [
    "chest pain", "shortness of breath", "abdominal pain", "fever",
    "fall / injury", "laceration", "altered mental status", "flu-like symptoms",
    "headache", "back pain", "cough", "dizziness",
]
PAYERS = ["Medicare", "Medicaid", "Commercial", "Self-Pay", "Managed-Care"]


def _resp_season_factor(d: date) -> float:
    """Multiplier > 1 during the winter respiratory season, peaking in January."""
    # Peak around day-of-year ~15 (mid Jan), trough mid-summer.
    doy = d.timetuple().tm_yday
    # cosine wave: max ~1.35 in January, min ~0.85 in July
    return 1.10 + 0.25 * math.cos(2 * math.pi * (doy - 15) / 365.0)


def _weekend(d: date) -> bool:
    return d.weekday() >= 5


def daterange(a: date, b: date):
    cur = a
    while cur <= b:
        yield cur
        cur += timedelta(days=1)


def _fake_name(rng: random.Random) -> str:
    return f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"


def build(db_path: Path | None = None) -> Path:
    rng = random.Random(SEED)
    db_path = db_path or settings.db_file
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_PATH.read_text())
    cur = conn.cursor()

    # ---- units ----
    unit_ids: dict[str, int] = {}
    for i, (code, name, utype, beds, ratio) in enumerate(UNITS, start=1):
        cur.execute(
            "INSERT INTO units VALUES (?,?,?,?,?,?)",
            (i, code, name, utype, beds, ratio),
        )
        unit_ids[code] = i

    # ---- beds ----
    bed_id = 1
    for code, _name, utype, beds, _ratio in UNITS:
        for n in range(1, beds + 1):
            iso = 1 if (utype in ("critical_care", "medical") and n <= 2) else 0
            cur.execute(
                "INSERT INTO beds VALUES (?,?,?,?)",
                (bed_id, unit_ids[code], f"{code}-{n:02d}", iso),
            )
            bed_id += 1

    census_id = 1
    staffing_id = 1
    admission_id = 1
    ed_id = 1

    for d in daterange(START_DATE, END_DATE):
        season = _resp_season_factor(d)
        weekend = _weekend(d)

        # ---------- ED visits for the day ----------
        base_ed = 42
        ed_count = int(rng.gauss(base_ed * season * (0.9 if weekend else 1.0), 6))
        ed_count = max(20, ed_count)
        admits_from_ed = 0
        for _ in range(ed_count):
            hour = min(23, max(0, int(rng.gauss(14, 5))))  # afternoon-skewed arrivals
            arrival = datetime(d.year, d.month, d.day, hour, rng.randint(0, 59))
            # ESI distribution: mostly 3-4, some 1-2 during surge
            esi = rng.choices([1, 2, 3, 4, 5], weights=[3, 12, 40, 33, 12])[0]
            # door-to-provider worsens with volume + acuity load
            crowd = max(0.6, ed_count / base_ed)
            d2p = int(max(3, rng.gauss(18 * crowd, 8)))
            los = int(max(30, rng.gauss(180 * crowd, 70) + (240 if esi <= 2 else 0)))
            lwbs = 1 if (d2p > 55 and rng.random() < 0.25) else 0
            if lwbs:
                disp = "lwbs"
            else:
                # higher acuity + surge -> more admits
                p_admit = 0.10 + (0.5 if esi <= 2 else 0.15 if esi == 3 else 0.03)
                p_admit *= season
                if rng.random() < min(0.85, p_admit):
                    disp = "admitted"
                    admits_from_ed += 1
                else:
                    disp = rng.choices(
                        ["discharged", "transferred", "ama"], weights=[92, 5, 3]
                    )[0]
            complaint = rng.choice(CHIEF_COMPLAINTS)
            mode = rng.choices(["walk_in", "ambulance", "police"], weights=[70, 28, 2])[0]
            cur.execute(
                "INSERT INTO ed_visits VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    ed_id, _fake_name(rng), arrival.isoformat(timespec="minutes"),
                    esi, complaint, d2p, los, disp, lwbs, mode,
                ),
            )
            ed_id += 1

        # ---------- Admissions for the day ----------
        # ED admits + elective (fewer on weekends) + a few transfers/direct
        elective = 0 if weekend else int(rng.gauss(10, 3))
        elective = max(0, elective)
        directs = int(rng.gauss(3, 2))
        day_admissions = admits_from_ed + elective + max(0, directs)
        for _ in range(day_admissions):
            src = rng.choices(
                ["ED", "elective", "transfer", "direct"],
                weights=[admits_from_ed + 1, elective + 1, 2, max(1, directs)],
            )[0]
            dx = rng.choice(DX_GROUPS)
            # route to a plausible unit
            if dx in ("heart_failure", "copd", "pneumonia", "sepsis", "diabetes", "renal", "uti", "cellulitis", "gi_bleed"):
                unit = rng.choices(["MED", "ICU", "OBS"], weights=[70, 12, 18])[0]
            elif dx in ("trauma_ortho", "post_surgical"):
                unit = rng.choices(["SURG", "ICU"], weights=[85, 15])[0]
            elif dx == "childbirth":
                unit = "OB"
            elif dx == "asthma":
                unit = rng.choices(["PEDS", "MED"], weights=[60, 40])[0]
            elif dx in ("stroke", "chest_pain"):
                unit = rng.choices(["ICU", "MED"], weights=[45, 55])[0]
            else:
                unit = "MED"
            age = rng.randint(0, 17) if unit == "PEDS" else (
                rng.randint(18, 45) if unit == "OB" else int(min(98, max(18, rng.gauss(62, 18))))
            )
            sex = "F" if unit == "OB" else rng.choice(["M", "F"])
            admit_hour = rng.randint(0, 23)
            admit_ts = datetime(d.year, d.month, d.day, admit_hour, rng.randint(0, 59))
            # LOS depends on dx / unit; ICU longer
            base_los = {"ICU": 96, "MED": 88, "SURG": 72, "PEDS": 48, "OB": 40, "OBS": 22}.get(unit, 72)
            los_h = round(max(6, rng.gauss(base_los, base_los * 0.4)), 1)
            disch_ts = admit_ts + timedelta(hours=los_h)
            # only mark discharged if within our window; else still admitted
            discharged = disch_ts.date() <= END_DATE
            readmit = 1 if (dx in ("heart_failure", "copd") and rng.random() < 0.22) or (rng.random() < 0.06) else 0
            payer = rng.choices(PAYERS, weights=[38, 22, 30, 5, 5])[0]
            cur.execute(
                "INSERT INTO admissions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    admission_id, _fake_name(rng), f"MRN{rng.randint(100000, 999999)}",
                    age, sex, unit_ids[unit], admit_ts.isoformat(timespec="minutes"),
                    disch_ts.isoformat(timespec="minutes") if discharged else None,
                    src, dx, los_h if discharged else None, readmit, payer,
                ),
            )
            admission_id += 1

        # ---------- Daily census + staffing per unit ----------
        for code, _name, utype, beds, ratio in UNITS:
            uid = unit_ids[code]
            # occupancy: surge lifts medical/critical/peds; OB steady; SURG lower on weekends
            surge = season if utype in ("medical", "critical_care", "pediatric") else 1.0
            wk = 0.85 if (utype == "surgical" and weekend) else 1.0
            base_occ = {"emergency": 0.75, "critical_care": 0.82, "medical": 0.85,
                        "surgical": 0.72, "pediatric": 0.6, "maternity": 0.65}.get(utype, 0.75)
            occ_frac = min(1.05, max(0.25, rng.gauss(base_occ * surge * wk, 0.08)))
            staffed = int(round(beds * min(1.0, rng.gauss(0.92, 0.05))))
            staffed = max(4, staffed)
            occupied = int(round(min(staffed * 1.02, beds * occ_frac)))
            occupied = max(0, occupied)
            # boarders: admitted patients stuck in ED when downstream is full
            boarders = 0
            if code in ("MED", "ICU") and occ_frac > 0.95:
                boarders = int(max(0, rng.gauss(6 * season, 3)))
            nurses = max(1, math.ceil(occupied / ratio) + rng.choice([-1, 0, 0, 1]))
            cur.execute(
                "INSERT INTO census_daily VALUES (?,?,?,?,?,?,?)",
                (census_id, d.isoformat(), uid, occupied, staffed, nurses, boarders),
            )
            census_id += 1

            for shift in ("day", "night"):
                need = math.ceil(occupied / ratio)
                # night shift chronically short in MED and ICU
                short = 0.85 if (shift == "night" and code in ("MED", "ICU")) else 1.0
                scheduled = max(1, math.ceil(need * rng.uniform(0.95, 1.1)))
                actual = max(1, int(round(scheduled * short * rng.uniform(0.85, 1.02))))
                agency = max(0, scheduled - actual) if rng.random() < 0.5 else 0
                actual_with_agency = actual + agency
                ot = round(max(0.0, (need - actual_with_agency)) * rng.uniform(2, 6), 1)
                techs = max(0, math.ceil(need / 2) + rng.choice([-1, 0, 1]))
                cur.execute(
                    "INSERT INTO staffing VALUES (?,?,?,?,?,?,?,?,?)",
                    (staffing_id, d.isoformat(), uid, shift, scheduled,
                     actual_with_agency, techs, agency, ot),
                )
                staffing_id += 1

    conn.commit()

    # ---- summary ----
    counts = {}
    for t in ("units", "beds", "census_daily", "admissions", "ed_visits", "staffing"):
        counts[t] = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    conn.close()

    total = sum(counts.values())
    print(f"Built {db_path}")
    for t, n in counts.items():
        print(f"  {t:<14} {n:>7,}")
    print(f"  {'TOTAL':<14} {total:>7,}")
    return db_path


if __name__ == "__main__":
    build()
