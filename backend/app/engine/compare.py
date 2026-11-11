"""Comparison of completed simulations. Pure Python: plain dicts in, a JSON-safe dict out.

Every simulation dict needs: id, scenario_id, scenario_name, scenario_version, environment_id, environment_name,
model_version, started_at, snapshot (frozen inputs) and result (stored outputs).
"""
from .modifications import graph_diff
from .rules import EPS, rnd

MIN_SIMS, MAX_SIMS = 2, 6


class ComparisonError(ValueError):
    """The selected simulations cannot be compared."""


def _label(s: dict) -> str:
    return f"{s['scenario_name']} v{s['scenario_version']} (#{s['id']})"


def _pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def _base_graph(snap: dict) -> tuple[list, list]:
    return snap.get("base_nodes") or snap["nodes"], snap.get("base_edges") or snap["edges"]


def check_compatible(sims: list[dict]) -> None:
    if not MIN_SIMS <= len(sims) <= MAX_SIMS:
        raise ComparisonError(f"Select between {MIN_SIMS} and {MAX_SIMS} simulations to compare.")
    if len({s["id"] for s in sims}) != len(sims):
        raise ComparisonError("Each simulation can only be selected once.")
    if len({s["environment_id"] for s in sims}) > 1:
        raise ComparisonError("These simulations belong to different environments. Only simulations of the same "
                              "environment can be compared.")
    versions = sorted({s["model_version"] for s in sims})
    if len(versions) > 1:
        raise ComparisonError(f"These simulations used different model versions ({', '.join(versions)}), "
                              "so their numbers are not comparable.")


def _score(rows: dict[int, dict], ids: set[int]) -> tuple[float, float]:
    """(adjusted score, weighted loss) over the given nodes."""
    num = den = 0.0
    for nid in sorted(ids):
        r = rows[nid]
        den += r["importance"] * r["baseline_level"]
        num += r["importance"] * max(0.0, r["baseline_level"] - r["level"])
    return (num / den if den > EPS else 0.0), num


def _targets(mod: dict, sim_nodes: list[dict], sim_edges: list[dict], mods: list[dict]) -> set[int]:
    """Node ids a modification acts on, looked up in the simulation's EFFECTIVE graph."""
    t = mod["type"]
    added_ids = {m["key"]: n["id"] for m in mods if m["type"] == "add_node"
                 for n in sim_nodes if n.get("added") and n["name"] == m["name"]}
    if t in ("set_capacity", "reduce_demand"):
        return {mod["node_id"]}
    if t == "add_node":
        return {n["id"] for n in sim_nodes if n.get("added") and n["name"] == mod["name"]}
    if t == "add_edge":
        return {r if isinstance(r, int) else added_ids.get(r, -1) for r in (mod["source"], mod["destination"])} - {-1}
    if t == "set_edge":
        e = next((e for e in sim_edges if e["id"] == mod["edge_id"]), None)
        return {e["destination_id"], e["source_id"]} if e else set()
    return set()


def _explain(ref: dict, sim: dict, rmap: dict, smap: dict, common: set[int], radj: float, sadj: float) -> dict:
    rl, sl = _label(ref), _label(sim)
    d = sadj - radj
    if abs(d) < 5e-7:
        headline = f"{sl} has the same modelled impact score as {rl} ({sadj:.3f}), measured on the {len(common)} nodes both runs share."
    else:
        headline = (f"{sl} has a {'lower' if d < 0 else 'higher'} modelled impact score than {rl}: {sadj:.3f} vs {radj:.3f} "
                    f"({d:+.3f}), measured on the {len(common)} nodes both runs share.")
    details: list[str] = []

    rmods, smods = ref["snapshot"].get("modification_labels", []), sim["snapshot"].get("modification_labels", [])
    only_s, only_r = [m for m in smods if m not in rmods], [m for m in rmods if m not in smods]
    if only_s:
        details.append(f"Modifications only in {sl}: " + "; ".join(only_s) + ".")
    if only_r:
        details.append(f"Modifications only in {rl}: " + "; ".join(only_r) + ".")
    revents, sevents = [e["label"] for e in ref["result"]["events"]], [e["label"] for e in sim["result"]["events"]]
    if sorted(revents) != sorted(sevents):
        details.append("The two runs use different events, so part of the difference comes from the disruption itself, "
                       "not only from any modification.")

    ru, su = ref["result"]["unserved"], sim["result"]["unserved"]
    for key in sorted(set(ru) | set(su)):
        a, b = ru.get(key, {}).get("scenario"), su.get(key, {}).get("scenario")
        if a is not None and b is not None and abs(a - b) > 1e-6:
            details.append(f"Unserved {key}: {a:g} -> {b:g}.")

    diffs = sorted(((smap[n]["level"] - rmap[n]["level"], n) for n in common
                    if abs(smap[n]["level"] - rmap[n]["level"]) > 1e-6),
                   key=lambda x: (-abs(x[0]), rmap[x[1]]["name"]))
    better = [x for x in diffs if x[0] > 0]
    worse = [x for x in diffs if x[0] < 0]
    details.append(f"Among the shared nodes, {len(better)} keep more service and {len(worse)} keep less in {sl}.")
    for delta, nid in diffs[:3]:
        details.append(f"'{rmap[nid]['name']}': {_pct(rmap[nid]['level'])} -> {_pct(smap[nid]['level'])} ({delta * 100:+.0f} pts).")

    if diffs:  # where do the two runs first diverge along the biggest change?
        delta, nid = diffs[0]
        loser = ref if delta > 0 else sim
        trace = next((t for t in loser["result"]["traces"] if t["node_id"] == nid), None)
        if trace and len(trace["path"]) > 1:
            div = next((p for p in trace["path"] if p in rmap and p in smap
                        and abs(rmap[p]["level"] - smap[p]["level"]) > 1e-6), None)
            if div is not None:
                details.append(
                    f"Why: in {_label(loser)} '{rmap[nid]['name']}' loses service along {' -> '.join(trace['path_names'])}. "
                    f"The two runs first differ at '{rmap[div]['name']}' ({_pct(rmap[div]['level'])} in {rl} vs "
                    f"{_pct(smap[div]['level'])} in {sl}).")
                near = {div} | {e["source_id"] for e in sim["snapshot"]["edges"] if e["destination_id"] == div}
                for mod, label in zip(sim["snapshot"].get("modifications", []), smods):
                    if label in only_s and near & _targets(mod, sim["snapshot"]["nodes"], sim["snapshot"]["edges"], sim["snapshot"].get("modifications", [])):
                        details.append(f"That point is directly affected by the modification: {label}.")
    return {"simulation_id": sim["id"], "reference_id": ref["id"], "headline": headline, "details": details}


def compare(sims: list[dict]) -> dict:
    check_compatible(sims)
    ref = sims[0]
    maps = [{r["node_id"]: r for r in s["result"]["node_results"]} for s in sims]
    common = set.intersection(*(set(m) for m in maps))
    union = set.union(*(set(m) for m in maps))
    scores = [_score(m, common) for m in maps]
    adj, wloss = [rnd(s[0]) for s in scores], [rnd(s[1]) for s in scores]

    # ---------- metric rows ----------
    def row(key, label, values, lower=None):
        best: list[int] = []
        nums = [v if v is not None else float("inf") for v in values]
        if lower and len(set(nums)) > 1:
            m = min(nums)
            best = [i for i, v in enumerate(nums) if v == m]
        return {"key": key, "label": label, "values": values, "lower_is_better": bool(lower), "best": best}

    mets = [s["result"]["metrics"] for s in sims]
    metrics = [
        row("impact_score", "Impact score (own baseline, all nodes)", [m["impact_score"] for m in mets], True),
        row("adjusted_score", f"Adjusted impact score ({len(common)} shared nodes)", adj, True),
        row("weighted_loss", "Weighted service lost (shared nodes)", wloss, True),
        row("affected_nodes", "Affected nodes", [m["affected_nodes"] for m in mets], True),
        row("direct_nodes", "Directly affected", [m["direct_nodes"] for m in mets]),
        row("indirect_nodes", "Indirectly affected", [m["indirect_nodes"] for m in mets]),
        row("failed_nodes", "Failed nodes", [m["failed_nodes"] for m in mets], True),
        row("degraded_nodes", "Degraded nodes", [m["degraded_nodes"] for m in mets], True),
        row("impact_hours", "Impact-hours", [m["impact_hours"] for m in mets], True),
        row("recovered_at", "Service restored at (h)", [m["recovered_at"] for m in mets], True),
        row("peak_time", "Peak step (h)", [m["peak_time"] for m in mets]),
        row("total_nodes", "Nodes in graph", [m["total_nodes"] for m in mets]),
    ]
    if all(v is None for v in metrics[9]["values"]):
        metrics[9]["best"] = []

    keys = sorted({k for s in sims for k in s["result"]["unserved"]})
    unserved = [{"key": k,
                 "baseline": [s["result"]["unserved"].get(k, {}).get("baseline") for s in sims],
                 "scenario": [s["result"]["unserved"].get(k, {}).get("scenario") for s in sims]} for k in keys]
    cats = sorted({c for m in mets for c in m["score_by_category"]})
    categories = [{"category": c, "values": [m["score_by_category"].get(c) for m in mets]} for c in cats]

    nodes = []
    for nid in union:
        present = [m.get(nid) for m in maps]
        first = next(r for r in present if r)
        lv = [r["level"] for r in present if r]
        nodes.append({
            "node_id": nid, "name": first["name"], "category": first["category"], "importance": first["importance"],
            "in_all": nid in common,
            "baseline_levels": [r["baseline_level"] if r else None for r in present],
            "levels": [r["level"] if r else None for r in present],
            "states": [r["state"] if r else None for r in present],
            "impacts": [r["impact"] if r else None for r in present],
            "spread": rnd(max(lv) - min(lv)),
        })
    nodes.sort(key=lambda n: (-n["spread"], n["name"]))

    # ---------- reliability warnings ----------
    warnings: list[dict] = []

    def warn(level, code, message):
        warnings.append({"level": level, "code": code, "message": message})

    for s in sims[1:]:
        a, b = _base_graph(ref["snapshot"]), _base_graph(s["snapshot"])
        if ref["snapshot"].get("base_hash") != s["snapshot"].get("base_hash") or ref["snapshot"].get("base_hash") is None:
            diff = graph_diff(a[0], a[1], b[0], b[1])
            if diff:
                warn("warning", "environment_edited",
                     f"The environment changed between {_label(ref)} and {_label(s)}: {'; '.join(diff)}. "
                     "Differences in the results may come from that edit, not from the scenarios.")
    if len({tuple(sorted(m)) for m in maps}) > 1:
        warn("info", "different_node_sets",
             "The runs do not contain the same nodes (modifications add nodes). The raw impact score divides by the total "
             f"weight of all nodes, so added nodes dilute it. Use the adjusted score, which only counts the {len(common)} shared nodes.")
    moved = [nid for nid in common if len({round(m[nid]["baseline_level"], 6) for m in maps}) > 1]
    if moved:
        names = ", ".join(sorted(maps[0][n]["name"] for n in moved)[:4])
        warn("warning", "baselines_differ",
             f"The baseline service level differs between runs at {len(moved)} shared node(s) ({names}). "
             "Each run's score is measured against its own baseline.")
    if len({tuple(sorted(e["label"] for e in s["result"]["events"])) for s in sims}) > 1:
        warn("info", "different_events",
             "The runs use different events. Differences reflect different disruptions, not only different mitigations.")
    if len({m["peak_time"] for m in mets}) > 1:
        warn("info", "different_peak_times",
             "Each run is compared at its own peak step, and the peaks occur at different times: "
             + ", ".join(f"{_label(s)} at t={s['result']['metrics']['peak_time']:g}h" for s in sims) + ".")
    for s in sims:
        if not s["result"]["solver"]["converged"]:
            warn("warning", "not_converged", f"The solver did not converge for {_label(s)}; its numbers are approximate.")
    shortfalls = [bool({w["code"] for w in s["result"]["warnings"]} & {"baseline_shortfall", "baseline_reduced"}) for s in sims]
    if any(shortfalls) and not all(shortfalls):
        warn("warning", "baseline_shortfall_differs",
             "Some runs already have a service shortfall in their baseline and others do not, so their scores are measured against different starting points.")
    if len({tuple(s["snapshot"]["scenario"].get("assumptions", [])) for s in sims}) > 1:
        warn("info", "different_assumptions", "The scenarios list different assumptions; read them before relying on the comparison.")

    return {
        "simulations": [{
            "id": s["id"], "label": _label(s), "scenario_id": s["scenario_id"], "scenario_name": s["scenario_name"],
            "scenario_version": s["scenario_version"], "environment_id": s["environment_id"],
            "environment_name": s["environment_name"], "model_version": s["model_version"],
            "started_at": s["started_at"], "evaluated_at": s["result"]["evaluated_at"],
            "events": [e["label"] for e in s["result"]["events"]],
            "modifications": s["snapshot"].get("modification_labels", []),
        } for s in sims],
        "reference_id": ref["id"],
        "common_node_count": len(common),
        "metrics": metrics, "unserved": unserved, "categories": categories, "nodes": nodes,
        "explanations": [_explain(ref, s, maps[0], maps[i], common, adj[0], adj[i]) for i, s in enumerate(sims) if i > 0],
        "warnings": warnings,
        "notes": ["No single metric decides which option is best: check the unserved demand, the failed nodes and the timeline too.",
                  "Differences are modelled, not predicted. Cost, physical feasibility and operational constraints are not modelled."],
    }