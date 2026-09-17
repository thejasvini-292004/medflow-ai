# Bed Management & Capacity Escalation Policy (OPS-BED-001)

## Purpose
Define how MedFlow General Hospital measures occupancy and escalates when
inpatient capacity is constrained, so that patient flow decisions are
consistent across shifts.

## Occupancy definitions
- **Occupancy %** is calculated as `occupied_beds / staffed_beds`, not against
  licensed beds. A unit can be at 100% occupancy while licensed beds remain
  empty if those beds are not staffed.
- **Boarders** are admitted patients who have a bed order but are still
  physically held in the Emergency Department because no staffed inpatient bed
  is available.

## Capacity escalation tiers
The house supervisor evaluates hospital-wide staffed occupancy every 4 hours.

- **GREEN (normal):** hospital staffed occupancy < 85% and ED boarders < 5.
  Routine flow. No action required.
- **YELLOW (surge watch):** staffed occupancy 85–92%, or ED boarders 5–9.
  Actions: expedite discharges before noon, open the OBS overflow pod, and
  notify the on-call nursing supervisor.
- **ORANGE (capacity alert):** staffed occupancy 93–97%, or ED boarders 10–14.
  Actions: activate the discharge lounge, pull agency/float RNs, delay elective
  surgical admissions that require an inpatient bed, and hold a bed-huddle every
  2 hours.
- **RED (capacity crisis):** staffed occupancy > 97%, or ED boarders >= 15, or
  any single inpatient unit over 100% of staffed beds. Actions: initiate ED
  diversion review (see OPS-ED-002), cancel non-urgent elective admissions,
  escalate to the Administrator-on-Call, and consider transfers out.

## Prioritization when beds are scarce
When more admissions are pending than beds available, prioritize in this order:
1. ICU step-downs that free a critical-care bed,
2. ED boarders with the longest ED length of stay,
3. patients with ESI 1–2 acuity awaiting an inpatient bed,
4. scheduled direct admits and transfers,
5. elective surgical admissions.

## Reporting expectations
Any unit sustaining > 95% staffed occupancy for more than 24 hours should be
flagged in the daily operations report with the count of boarders and the
number of discharges completed before noon.
