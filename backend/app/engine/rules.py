"""Constants and documented assumptions of the NEXUS simulation model. Pure Python."""

RESOURCE_CATEGORIES = frozenset({"electricity", "water", "communication"})
STATE_FACTORS = {"operational": 1.0, "degraded": 0.5, "failed": 0.0, "maintenance": 0.0}
OUTAGE_EVENTS = frozenset({"failure", "road_closure", "maintenance"})

EPS = 1e-9               # numerical tolerance
MAX_ITERATIONS = 200     # sweeps per solve before giving up on convergence
MAX_WORK = 3_000_000     # node + edge evaluations allowed per simulation

FORMULA = ("impact_score = sum(w_i * max(0, L_base_i - L_i)) / sum(w_i * L_base_i), "
           "where w_i is the node's importance weight and L is its service level (0 to 1)")


def rnd(x: float) -> float:
    return round(x, 6) + 0.0  # "+ 0.0" turns -0.0 into 0.0


ASSUMPTIONS = [
    "All values are synthetic or user-provided. Nothing is calibrated against real infrastructure.",
    "Each time step is a steady-state snapshot: effects spread through the whole graph instantly. "
    "Delays, ramp-up and transient behaviour are not modelled.",
    "A node's own factor comes from its baseline state (operational 1, degraded 0.5, failed or maintenance 0) "
    "and its active events. Any outage dominates; overlapping reductions multiply.",
    "A required supplier limits a node (bottleneck). Partial suppliers multiply their losses. "
    "Backup suppliers add to the delivery, capped at full service. Strength scales how strongly a loss is passed on.",
    "Edges between nodes of the same resource category (e.g. electricity to electricity) pass quantities: "
    "inflow = sum of upstream output x strength, limited by the node's capacity.",
    "When a resource node delivers less than its dependents request, every dependent receives the same fraction.",
    "Demand is nominal: dependents keep requesting their declared demand even when degraded or down.",
    "Circular dependencies are resolved by iterating to the greatest fixed point; "
    "mutual dependence alone never causes a failure.",
    "Importance weights and dependency strengths are judgements, not measurements.",
]

LIMITATIONS = [
    "The impact score is a weighted share of baseline service lost. It is a modelled index, "
    "not a probability, cost or safety rating.",
    "A root-cause loss and its downstream losses are counted separately, so long dependency chains score higher by design.",
    "Because demand is not reduced when a consumer is down, shortfalls can be overstated.",
    "No human behaviour, repair logistics, cost or physical feasibility is modelled.",
    "This is an educational model, not a validated or certified engineering model.",
]