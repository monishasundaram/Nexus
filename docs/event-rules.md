# Scenario event rules

Time is measured in hours. An event is active during [start, start + duration); with no duration it stays active for the whole run.
Events with the same start time are processed in list order (start time, then id).

| Event | Parameter | Duration | Allowed targets | Effect while active |
|---|---|---|---|---|
| failure | none | optional | any | capacity -> 0, state failed |
| capacity_reduction | reduction_pct (0-100] | optional | any | capacity x (1 - pct/100) |
| road_closure | none | optional | road | same as failure |
| resource_shortage | shortage_pct (0-100] | optional | electricity, water, communication, generic | same as capacity_reduction |
| maintenance | none | required | any | capacity -> 0, state maintenance |
| recovery | none | not allowed | any | state -> operational, capacity -> baseline value; ends all active effects on that node |

## Combining overlapping effects on one node (implemented in Phase 4)
- Any failure, closure or maintenance dominates: capacity is 0.
- Overlapping reductions multiply: remaining = product of (1 - pct/100).

## Versioning
- A scenario starts as a **draft** (editable in place).
- **Finalize** validates and locks it. Final versions never change, so simulations stay reproducible.
- **New version** copies a scenario into the next version number as a draft.
- Name changes are blocked once a scenario has more than one version.