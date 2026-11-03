"""Impact scoring and capacity accounting. Pure Python."""
from .rules import EPS, RESOURCE_CATEGORIES, rnd


def impact_score(nodes: dict[int, dict], base: dict, vals: dict, ids=None) -> float:
    """Weighted share of baseline service lost, between 0 and 1."""
    num = den = 0.0
    for nid in sorted(nodes) if ids is None else ids:
        w = nodes[nid]["importance"]
        den += w * base[nid].lvl
        num += w * max(0.0, base[nid].lvl - vals[nid].lvl)
    return num / den if den > EPS else 0.0


def score_by_category(nodes: dict[int, dict], base: dict, vals: dict) -> dict[str, float]:
    groups: dict[str, list[int]] = {}
    for nid in sorted(nodes):
        groups.setdefault(nodes[nid]["category"], []).append(nid)
    return {c: rnd(impact_score(nodes, base, vals, ids)) for c, ids in sorted(groups.items())}


def capacity_table(net, base: dict, vals: dict) -> list[dict]:
    rows = []
    for nid in sorted(net.nodes):
        n = net.nodes[nid]
        if n["category"] not in RESOURCE_CATEGORIES or net.cap[nid] <= 0:
            continue
        demand, b, v = net.demand[nid], base[nid], vals[nid]
        rows.append({
            "node_id": nid, "name": n["name"], "category": n["category"],
            "unit": str((n.get("meta") or {}).get("unit", "")),
            "nominal_capacity": net.cap[nid],
            "baseline_output": rnd(b.out), "scenario_output": rnd(v.out),
            "demand": demand,
            "baseline_unserved": rnd(max(0.0, demand - b.out)),
            "scenario_unserved": rnd(max(0.0, demand - v.out)),
            "baseline_level": rnd(b.lvl), "scenario_level": rnd(v.lvl),
        })
    return rows


def unserved_totals(rows: list[dict]) -> dict[str, dict]:
    totals: dict[str, dict] = {}
    for row in rows:
        if row["demand"] <= 0:
            continue
        key = f"{row['category']} ({row['unit']})" if row["unit"] else row["category"]
        t = totals.setdefault(key, {"baseline": 0.0, "scenario": 0.0})
        t["baseline"] += row["baseline_unserved"]
        t["scenario"] += row["scenario_unserved"]
    return {k: {"baseline": rnd(v["baseline"]), "scenario": rnd(v["scenario"])} for k, v in sorted(totals.items())}