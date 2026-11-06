# Simulation model v1.0.0

This file defines what the engine does. If the code and this file disagree, that is a bug.

## 1. Time
Time is in hours. The engine evaluates one **steady state** at t=0 and at every moment an event starts or ends.
Effects spread through the whole graph instantly inside a step. The headline results (node table, traces,
capacity table) are for the **peak step**: highest impact score, then most active events, then earliest.
The timeline lists every step.

## 2. A node's own factor
Baseline: operational 1, degraded 0.5, failed 0, maintenance 0.
Active events then change it: failure, road closure and maintenance multiply by 0; capacity reduction and
resource shortage multiply by (1 - pct/100). Events are processed by (start time, id). A recovery ends every
effect started before it and restores the node to operational.

## 3. Edges (A -> B means A supplies B)
Let d be A's service level and s the edge strength.

| Edge | Between | Effect on B |
|---|---|---|
| required | different categories | bottleneck: min over required edges of 1 - s(1 - d) |
| partial | different categories | multiplies: product of 1 - s(1 - d) |
| backup | different categories | adds s*d to the required level, capped at 1 (alone: min(1, sum s*d)) |
| any type | both nodes in the same resource category (electricity, water, communication) | quantity flow: inflow = sum of out(A)*s; flow level = min(1, inflow / capacity(B)) |

## 4. Node equations
- availability a(B) = min(own factor, flow level, required level) x partial factor
- output out(B) = capacity(B) x a(B)
- service level L(B) = min(1, out(B) / D(B)) if B is a resource node with demand D(B) > 0, otherwise a(B)

## 5. Demand
A node's demands come from `meta.demands` (e.g. {"electricity": 60}). If that key is absent, `demand` is used
when the node has exactly one resource-type supplier; otherwise it is ignored with a warning.
D(S) is the sum of the demands that S's dependents place on S's resource (each pair counted once).
When out(S) < D(S) every dependent receives the same fraction out/D (proportional share).
Unserved demand = max(0, D - out). Demand is nominal: it is not reduced when a dependent is down.

## 6. Cycles
The solver starts from the best case (all nodes at their own factor) and sweeps suppliers-before-dependents
until the largest change is below 1e-9, at most 200 sweeps. The update rules are monotone, so this converges
to the greatest fixed point. If it does not converge, the last iterate is reported with a warning.
A work budget (3,000,000 node and edge evaluations per simulation) stops runaway runs.

## 7. Impact score
score = sum(w_i * max(0, L_base_i - L_i)) / sum(w_i * L_base_i), w_i = importance.
It is the weighted share of baseline service lost (0 to 1). It is a modelled index, not a probability.
Also reported: per-category scores, the peak and final score, the time service recovers, and
impact-hours (score x duration summed until the last event change).

## 8. Direct, indirect, traces
- **Directly affected:** service dropped and an active event lowered the node's own factor.
- **Indirectly affected:** service dropped without such an event.
- **Absorbed:** an event lowered the own factor but spare capacity kept service unchanged.
- **Trace:** for each indirect node, the supplier edge whose reset to baseline restores the most service
  (counterfactual). Following those edges back gives the path from the originating event.

## 9. Worked example: primary grid failure on NEXUS Campus
- Primary Grid Supply output 0. Main Substation inflow = 0 + 400 kW (diesel) x 0.8 = 320 kW, capacity 1000, so a = 0.32.
- Demand on the substation: 60 + 30 + 20 + 680 = 790 kW. Service level = 320 / 790 = 40.5%.
- Every required consumer of the substation gets 40.5%. Pump House output falls with it, so the tank receives about 202.5 kL/day against 330 requested.

## 10. Limits
See `LIMITATIONS` in `engine/rules.py`. Importance weights and strengths are assumptions; test them with the
sensitivity analysis in Phase 7.