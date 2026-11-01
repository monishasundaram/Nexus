"""Scenario validation. Pure Python: no web framework or database imports."""
from collections import Counter, defaultdict

from ..config import MAX_EVENTS
from .events import DISRUPTIONS, EVENT_TYPES, check_event_shape, event_window


def _issue(level, code, message, node_ids=(), event_ids=()):
    return {"level": level, "code": code, "message": message,
            "node_ids": list(node_ids), "event_ids": list(event_ids)}


def _describe(e: dict, by_id: dict) -> str:
    spec = EVENT_TYPES.get(e["event_type"])
    kind = spec["label"] if spec else str(e["event_type"])
    node = by_id.get(e["target_node_id"])
    target = f"'{node['name']}'" if node else "an unknown node"
    return f"{kind} on {target} at t={e['start_time']:g}"


def validate_scenario(nodes: list[dict], events: list[dict], max_events: int = MAX_EVENTS) -> dict:
    issues: list[dict] = []
    by_id = {n["id"]: n for n in nodes}

    if not events:
        issues.append(_issue("error", "no_events",
                             "The scenario has no events. Add at least one event to run it."))
    if len(events) > max_events:
        issues.append(_issue("error", "too_many_events",
                             f"The scenario has {len(events)} events; the limit is {max_events}."))

    # --- per-event checks ---
    usable: list[dict] = []  # events with a valid target
    for e in events:
        eid, text = e["id"], _describe(e, by_id)
        spec = EVENT_TYPES.get(e["event_type"])
        for problem in check_event_shape(e["event_type"], e["params"], e["duration"]):
            issues.append(_issue("error", "invalid_event", f"{text}: {problem}", event_ids=[eid]))
        if e["start_time"] < 0:
            issues.append(_issue("error", "negative_time", f"{text}: start time cannot be negative.",
                                 event_ids=[eid]))
        tid = e["target_node_id"]
        node = by_id.get(tid)
        if node is None:
            issues.append(_issue("error", "missing_target",
                                 f"{text}: the target node was never set or no longer exists.",
                                 event_ids=[eid]))
            continue
        if spec and spec["targets"] and node["category"] not in spec["targets"]:
            issues.append(_issue("error", "wrong_target_category",
                                 f"{text}: this event type needs a target in "
                                 f"[{', '.join(spec['targets'])}], but '{node['name']}' is '{node['category']}'.",
                                 [tid], [eid]))
            continue
        usable.append(e)

    # --- duplicates ---
    seen: dict[str, int] = {}
    for e in usable:
        key = str((e["event_type"], e["target_node_id"], e["start_time"], e["duration"],
                   sorted(e["params"].items())))
        if key in seen:
            issues.append(_issue("warning", "duplicate_event",
                                 f"{_describe(e, by_id)} appears more than once.",
                                 [e["target_node_id"]], [seen[key], e["id"]]))
        else:
            seen[key] = e["id"]

    # --- events that change nothing ---
    for e in usable:
        node = by_id[e["target_node_id"]]
        if e["event_type"] in ("failure", "road_closure") and node["state"] in ("failed", "maintenance"):
            issues.append(_issue("info", "already_down",
                                 f"{_describe(e, by_id)}: the node is already '{node['state']}' in the baseline.",
                                 [node["id"]], [e["id"]]))
        if e["event_type"] in ("capacity_reduction", "resource_shortage") and node["capacity"] == 0:
            issues.append(_issue("warning", "zero_capacity",
                                 f"{_describe(e, by_id)}: the node has capacity 0, so a reduction changes nothing.",
                                 [node["id"]], [e["id"]]))

    # --- overlapping disruptions on the same node ---
    by_node: dict[int, list[dict]] = defaultdict(list)
    for e in usable:
        if e["event_type"] in DISRUPTIONS:
            by_node[e["target_node_id"]].append(e)
    for nid, group in by_node.items():
        involved: set[int] = set()
        for i, a in enumerate(group):
            a0, a1 = event_window(a["start_time"], a["duration"])
            for b in group[i + 1:]:
                b0, b1 = event_window(b["start_time"], b["duration"])
                if a0 < b1 and b0 < a1:
                    involved.update((a["id"], b["id"]))
        if involved:
            issues.append(_issue("warning", "overlapping_events",
                                 f"{len(involved)} events overlap in time on '{by_id[nid]['name']}'. "
                                 "Their effects are combined by the rule in docs/event-rules.md.",
                                 [nid], sorted(involved)))

    # --- recoveries with nothing to recover ---
    for r in usable:
        if r["event_type"] != "recovery":
            continue
        node = by_id[r["target_node_id"]]
        active = any(d["start_time"] <= r["start_time"] < event_window(d["start_time"], d["duration"])[1]
                     for d in by_node.get(r["target_node_id"], []))
        if not active and node["state"] == "operational":
            issues.append(_issue("warning", "recovery_without_disruption",
                                 f"{_describe(r, by_id)}: nothing is disrupted on this node at that time, "
                                 "so the recovery changes nothing.", [node["id"]], [r["id"]]))

    # --- simultaneous disruptions (informational) ---
    starts: dict[float, list[dict]] = defaultdict(list)
    for e in usable:
        if e["event_type"] in DISRUPTIONS:
            starts[e["start_time"]].append(e)
    for t, group in sorted(starts.items()):
        if len(group) > 1:
            issues.append(_issue("info", "simultaneous_disruptions",
                                 f"{len(group)} disruptions start together at t={t:g}; "
                                 "they are treated as one multi-disruption scenario.",
                                 sorted({g["target_node_id"] for g in group}), [g["id"] for g in group]))

    rank = {"error": 0, "warning": 1, "info": 2}
    issues.sort(key=lambda i: rank[i["level"]])
    errors = sum(1 for i in issues if i["level"] == "error")
    return {
        "valid": errors == 0,
        "error_count": errors,
        "warning_count": sum(1 for i in issues if i["level"] == "warning"),
        "issues": issues,
        "stats": {
            "event_count": len(events),
            "event_types": dict(Counter(e["event_type"] for e in events)),
            "targets": len({e["target_node_id"] for e in events if e["target_node_id"] is not None}),
            "last_start": max((e["start_time"] for e in events), default=0),
        },
    }