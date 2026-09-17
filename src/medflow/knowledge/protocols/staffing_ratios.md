# Nurse Staffing Ratio & Coverage Policy (OPS-STAFF-003)

## Target nurse-to-patient ratios
Ratios follow California-style minimums and are enforced per shift, per unit:

| Unit | Unit type | Max patients per RN |
|------|-----------|---------------------|
| ICU  | Critical care | 2:1 |
| ED   | Emergency | 4:1 (1:1 for ESI 1) |
| PEDS | Pediatric | 4:1 |
| OB   | Labor & delivery | 3:1 (1:1 in active labor) |
| MED  | Medical / telemetry | 5:1 |
| SURG | Surgical | 5:1 |
| OBS  | Observation | 5:1 |

`target_nurse_ratio` in the operational data is the patients-per-nurse target
for each unit.

## Coverage rules
- **Actual RNs** counts employed plus agency RNs on the shift.
- A shift is considered **understaffed** when
  `patients / actual_RNs > target_nurse_ratio`, i.e. each nurse is carrying
  more patients than the ratio allows.
- Agency (traveler) RNs may be used to close gaps but should not exceed **20%**
  of a unit's staffed RNs on a shift without nursing-director approval.
- **Overtime hours** above 12 per RN per week is a burnout risk flag and should
  be reviewed by the unit manager.

## Night-shift attention
Night shifts historically run leaner. Any unit whose night shift is understaffed
(per the rule above) on more than 8 days in a rolling 30-day window must have a
staffing corrective plan filed with the CNO.

## Escalation
If a unit cannot meet ratio for an upcoming shift, escalate at least 4 hours
before shift start: (1) offer voluntary overtime, (2) float a qualified RN from
a lower-acuity unit, (3) request agency coverage, (4) as a last resort, cap
admissions to the unit until ratio can be restored.
