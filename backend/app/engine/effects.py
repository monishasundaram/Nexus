"""Turns scenario events into per-node own factors at a point in time. Pure Python."""
from .events import EVENT_TYPES, event_window
from .rules import OUTAGE_EVENTS, STATE_FACTORS


def effect_factor(event: dict) -> float:
    kind = event["event_type"]
    if kind in OUTAGE_EVENTS:
        return 0.0
    pct = float(event["params"][EVENT_TYPES[kind]["param"]])
    return max(0.0, 1.0 - pct / 100.0)


def baseline_factors(nodes: dict[int, dict]) -> dict[int, float]:
    return {nid: STATE_FACTORS[n["state"]] for nid, n in nodes.items()}


def own_factors(nodes: dict[int, dict], events: list[dict], t: float) -> dict[int, tuple[float, list[int]]]:
    """{node_id: (own_factor, ids of the disruptions active on that node)} at time t."""
    base = baseline_factors(nodes)
    restored: set[int] = set()
    active: dict[int, list[dict]] = {nid: [] for nid in nodes}
    for e in sorted(events, key=lambda e: (e["start_time"], e["id"])):
        nid = e["target_node_id"]
        if nid not in nodes or e["start_time"] > t:
            continue
        if e["event_type"] == "recovery":
            active[nid] = []          # a recovery ends everything started before it
            restored.add(nid)         # and restores the node to operational
        elif t < event_window(e["start_time"], e["duration"])[1]:
            active[nid].append(e)
    result = {}
    for nid in nodes:
        factor = 1.0 if nid in restored else base[nid]
        for e in active[nid]:
            factor *= effect_factor(e)
        result[nid] = (factor, [e["id"] for e in active[nid]])
    return result


def change_times(events: list[dict]) -> list[float]:
    """t=0 plus every moment an event starts or ends."""
    times = {0.0}
    for e in events:
        times.add(float(e["start_time"]))
        if e["duration"] is not None:
            times.add(float(e["start_time"]) + float(e["duration"]))
    return sorted(times)