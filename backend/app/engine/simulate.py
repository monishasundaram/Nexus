"""Simulation orchestrator. Pure Python: plain dicts in, a JSON-safe dict out."""
from collections import Counter

from ..config import MODEL_VERSION
from .effects import baseline_factors, change_times, own_factors
from .propagation import Network
from .rules import ASSUMPTIONS, EPS, FORMULA, LIMITATIONS, MAX_ITERATIONS, MAX_WORK, rnd
from .scenario_validation import validate_scenario
from .scoring import capacity_table, impact_score, score_by_category, unserved_totals
from .trace import analyse, event_label
from .validation import validate_graph


class SimulationInputError(ValueError):
    def __init__(self, messages: list[str]):
        super().__init__("; ".join(messages))
        self.messages = messages


def _warn(source: str, level: str, code: str, message: str) -> dict:
    return {"source": source, "level": level, "code": code, "message": message}


def _counts(net, base, vals) -> tuple[int, int]:
    affected = failed = 0
    for nid in net.nodes:
        if base[nid].lvl - vals[nid].lvl > EPS:
            affected += 1
            failed += vals[nid].lvl <= EPS
    return affected, failed


def _baseline_warnings(net, base, own_base) -> list[dict]:
    out = []
    for nid in sorted(net.nodes):
        n, b = net.nodes[nid], base[nid]
        if b.lvl >= 1 - EPS or own_base[nid] < 1 - EPS:
            continue
        if nid in net.quantity and b.out < net.demand[nid] - EPS:
            unit = str((n.get("meta") or {}).get("unit", ""))
            unit = f" {unit}" if unit else ""
            out.append(_warn("engine", "warning", "baseline_shortfall",
                             f"'{n['name']}' delivers {b.out:g} of the {net.demand[nid]:g}{unit} its dependents request "
                             f"in the baseline (service level {b.lvl:.0%}). Results are measured against this baseline."))
        else:
            out.append(_warn("engine", "warning", "baseline_reduced",
                             f"'{n['name']}' is below full service in the baseline ({b.lvl:.0%}) "
                             "because of its suppliers or capacity wiring."))
    return out


def run_simulation(nodes: list[dict], edges: list[dict], events: list[dict], *,
                   max_iterations: int = MAX_ITERATIONS, max_work: int = MAX_WORK) -> dict:
    # 1. validate
    graph_report = validate_graph(nodes, edges)
    scenario_report = validate_scenario(nodes, events)
    problems = [i["message"] for i in graph_report["issues"] + scenario_report["issues"] if i["level"] == "error"]
    if problems:
        raise SimulationInputError(problems)
    warnings = [_warn(src, i["level"], i["code"], i["message"])
                for src, rep in (("graph", graph_report), ("scenario", scenario_report))
                for i in rep["issues"]]

    net = Network(nodes, edges, max_work=max_work)
    warnings += [_warn("engine", "warning", n["code"], n["message"]) for n in net.notes]
    ordered = sorted(events, key=lambda e: (e["start_time"], e["id"]))
    events_by_id = {e["id"]: e for e in ordered}
    names = {nid: n["name"] for nid, n in net.nodes.items()}

    # 2-3. baseline snapshot and evaluation (inputs are never modified)
    own_base = baseline_factors(net.nodes)
    base, sweeps, ok = net.solve(own_base, max_iterations)
    solver = {"max_sweeps": sweeps, "converged": ok, "steps": 0}
    if not ok:
        warnings.append(_warn("engine", "warning", "not_converged",
                              f"The baseline did not converge within {max_iterations} sweeps; the last iterate is used."))
    warnings += _baseline_warnings(net, base, own_base)

    # 4-5. apply events and propagate, one steady state per change point
    steps = []
    for t in change_times(ordered):
        own = own_factors(net.nodes, ordered, t)
        vals, n_sweeps, ok = net.solve({nid: f for nid, (f, _) in own.items()}, max_iterations)
        solver["max_sweeps"] = max(solver["max_sweeps"], n_sweeps)
        if not ok:
            solver["converged"] = False
            warnings.append(_warn("engine", "warning", "not_converged",
                                  f"At t={t:g}h the solver did not converge within {max_iterations} sweeps; "
                                  "the last iterate is reported."))
        affected, failed = _counts(net, base, vals)
        steps.append({
            "time": t, "own": own, "vals": vals, "score": impact_score(net.nodes, base, vals),
            "active": sorted({i for _, ids in own.values() for i in ids}),
            "starting": [e["id"] for e in ordered if e["start_time"] == t],
            "ending": [e["id"] for e in ordered
                       if e["duration"] is not None and float(e["start_time"]) + float(e["duration"]) == t],
            "affected": affected, "failed": failed, "degraded": affected - failed,
        })
    solver["steps"] = len(steps)

    # peak step: highest score, then most active events, then earliest
    peak_i, peak_key = 0, None
    for i, s in enumerate(steps):
        key = (round(s["score"], 12), len(s["active"]))
        if peak_key is None or key > peak_key:
            peak_i, peak_key = i, key
    peak, last = steps[peak_i], steps[-1]

    # 6-8. node states, traces, impact, capacity
    node_results, traces = analyse(net, base, peak["vals"], peak["own"], own_base, events_by_id)
    capacity = capacity_table(net, base, peak["vals"])
    worse = [r for r in node_results if r["trend"] == "worse"]
    improved = sum(r["trend"] == "better" for r in node_results)

    recovered_at = None
    if peak["score"] > EPS:
        recovered_at = next((s["time"] for s in steps[peak_i + 1:] if s["score"] <= EPS), None)
    impact_hours = sum(steps[i]["score"] * (steps[i + 1]["time"] - steps[i]["time"]) for i in range(len(steps) - 1))

    metrics = {
        "total_nodes": len(node_results),
        "affected_nodes": len(worse),
        "direct_nodes": sum(r["impact"] == "direct" for r in node_results),
        "indirect_nodes": sum(r["impact"] == "indirect" for r in node_results),
        "failed_nodes": sum(r["state"] in ("failed", "maintenance") for r in worse),
        "degraded_nodes": sum(r["state"] == "degraded" for r in worse),
        "improved_nodes": improved,
        "impact_score": rnd(peak["score"]),
        "peak_time": peak["time"], "final_time": last["time"], "final_score": rnd(last["score"]),
        "recovered_at": recovered_at, "impact_hours": rnd(impact_hours),
        "affected_categories": dict(sorted(Counter(r["category"] for r in worse).items())),
        "score_by_category": score_by_category(net.nodes, base, peak["vals"]),
    }

    for r in node_results:
        if r["absorbed"]:
            warnings.append(_warn("engine", "info", "event_absorbed",
                                  f"'{r['name']}' was directly hit but kept full service: spare capacity absorbs the event."))
    if not worse and not improved:
        warnings.append(_warn("engine", "info", "no_impact", "The scenario caused no modelled loss of service."))
    if sum(n["importance"] * base[nid].lvl for nid, n in net.nodes.items()) <= EPS:
        warnings.append(_warn("engine", "warning", "no_baseline_service",
                              "No node delivers service in the baseline, so the impact score is 0 by definition."))

    timeline = [{
        "time": s["time"], "impact_score": rnd(s["score"]), "affected_nodes": s["affected"],
        "failed_nodes": s["failed"], "degraded_nodes": s["degraded"],
        "active_event_ids": s["active"], "starting": s["starting"], "ending": s["ending"],
    } for s in steps]
    events_out = [{"id": e["id"], "type": e["event_type"], "label": event_label(e, names),
                   "target_node_id": e["target_node_id"], "params": e["params"],
                   "start_time": e["start_time"], "duration": e["duration"]} for e in ordered]

    return {
        "model_version": MODEL_VERSION, "evaluated_at": peak["time"], "metrics": metrics,
        "node_results": node_results, "traces": traces, "capacity": capacity,
        "unserved": unserved_totals(capacity), "timeline": timeline, "events": events_out,
        "solver": solver, "warnings": warnings,
        "assumptions": list(ASSUMPTIONS), "limitations": list(LIMITATIONS), "formula": FORMULA,
    }