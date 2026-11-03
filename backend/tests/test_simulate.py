import copy
import json

import pytest

from app.engine.propagation import SimulationLimitError
from app.engine.simulate import SimulationInputError, run_simulation


def node(i, name, cat="generic", cap=0.0, imp=0.5, demands=None, state="operational"):
    meta = {"demands": demands} if demands is not None else {}
    return {"id": i, "name": name, "category": cat, "state": state, "capacity": cap,
            "demand": 0.0, "importance": imp, "meta": meta}


def edge(i, s, d, rel="required", strength=1.0):
    return {"id": i, "source_id": s, "destination_id": d, "relationship_type": rel,
            "strength": strength, "capacity": None}


def ev(i, kind, target, start=0.0, duration=None, **params):
    return {"id": i, "event_type": kind, "target_node_id": target, "params": params,
            "start_time": start, "duration": duration}


def run(nodes, edges, events, **kw):
    return run_simulation(nodes, edges, events, **kw)


def by_id(result):
    return {n["node_id"]: n for n in result["node_results"]}


def codes(result):
    return {w["code"] for w in result["warnings"]}


CHAIN = ([node(1, "A"), node(2, "B"), node(3, "C")], [edge(1, 1, 2), edge(2, 2, 3)])


def test_failure_spreads_down_a_chain():
    r = run(*CHAIN, [ev(1, "failure", 1)])
    m = r["metrics"]
    assert (m["total_nodes"], m["affected_nodes"], m["direct_nodes"], m["indirect_nodes"]) == (3, 3, 1, 2)
    assert m["failed_nodes"] == 3 and m["degraded_nodes"] == 0
    assert m["impact_score"] == pytest.approx(1.0)
    assert m["affected_categories"] == {"generic": 3}
    n = by_id(r)
    assert [n[i]["impact"] for i in (1, 2, 3)] == ["direct", "indirect", "indirect"]
    traces = {t["node_id"]: t for t in r["traces"]}
    assert traces[3]["path"] == [1, 2, 3] and traces[3]["edge_ids"] == [1, 2] and traces[3]["event_ids"] == [1]
    assert traces[1]["path"] == [1] and traces[1]["impact"] == "direct"
    assert "directly affected" in traces[1]["explanation"]
    assert "Chain: A -> B -> C" in traces[3]["explanation"]


def test_the_score_is_weighted_by_importance():
    nodes = [node(1, "A", imp=1.0), node(2, "B", imp=0.5)]
    r = run(nodes, [edge(1, 1, 2, "partial", 0.4)], [ev(1, "failure", 1)])
    # loss: A 1.0, B 0.4  ->  (1.0*1.0 + 0.5*0.4) / (1.0*1 + 0.5*1) = 1.2 / 1.5
    assert r["metrics"]["impact_score"] == pytest.approx(0.8)
    assert (r["metrics"]["failed_nodes"], r["metrics"]["degraded_nodes"]) == (1, 1)
    assert by_id(r)[2]["level"] == pytest.approx(0.6) and by_id(r)[2]["state"] == "degraded"


def test_spare_capacity_absorbs_an_event():
    nodes = [node(1, "Supply", "electricity", 100), node(2, "C1", "building", demands={"electricity": 30}),
             node(3, "C2", "building", demands={"electricity": 30})]
    r = run(nodes, [edge(1, 1, 2), edge(2, 1, 3)], [ev(1, "capacity_reduction", 1, reduction_pct=20)])
    assert r["metrics"]["affected_nodes"] == 0 and r["metrics"]["impact_score"] == 0
    assert by_id(r)[1]["absorbed"] and by_id(r)[1]["impact"] == "none"
    assert "event_absorbed" in codes(r)
    row = r["capacity"][0]
    assert (row["baseline_output"], row["scenario_output"]) == (100, 80)


def test_capacity_and_unserved_demand():
    nodes = [node(1, "Supply", "electricity", 100), node(2, "C1", "building", demands={"electricity": 50}),
             node(3, "C2", "building", demands={"electricity": 50})]
    r = run(nodes, [edge(1, 1, 2), edge(2, 1, 3)], [ev(1, "capacity_reduction", 1, reduction_pct=50)])
    row = r["capacity"][0]
    assert (row["demand"], row["baseline_unserved"], row["scenario_unserved"]) == (100, 0, 50)
    assert r["unserved"] == {"electricity": {"baseline": 0, "scenario": 50}}
    m = r["metrics"]
    assert m["affected_nodes"] == 3 and m["direct_nodes"] == 1
    assert m["impact_score"] == pytest.approx(0.5)


def test_same_input_gives_identical_output_and_inputs_are_not_modified():
    nodes, edges = CHAIN
    events = [ev(1, "capacity_reduction", 1, reduction_pct=30), ev(2, "failure", 2, start=4, duration=2)]
    before = copy.deepcopy((nodes, edges, events))
    a, b = run(nodes, edges, events), run(nodes, edges, events)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert (nodes, edges, events) == before


def test_recovery_ends_the_impact():
    nodes = [node(1, "A"), node(2, "B")]
    r = run(nodes, [edge(1, 1, 2)], [ev(1, "failure", 1), ev(2, "recovery", 1, start=5)])
    assert [(s["time"], s["impact_score"]) for s in r["timeline"]] == [(0.0, 1.0), (5.0, 0.0)]
    m = r["metrics"]
    assert (m["peak_time"], m["final_score"], m["recovered_at"], m["impact_hours"]) == (0.0, 0.0, 5.0, 5.0)
    assert by_id(r)[1]["state"] == "failed"


def test_maintenance_window():
    nodes = [node(1, "A"), node(2, "B")]
    r = run(nodes, [edge(1, 1, 2)], [ev(1, "maintenance", 1, start=2, duration=3)])
    assert [s["time"] for s in r["timeline"]] == [0.0, 2.0, 5.0]
    assert [s["impact_score"] for s in r["timeline"]] == [0.0, 1.0, 0.0]
    m = r["metrics"]
    assert (m["peak_time"], m["recovered_at"], m["impact_hours"]) == (2.0, 5.0, 3.0)
    assert by_id(r)[1]["state"] == "maintenance" and by_id(r)[2]["state"] == "failed"
    assert r["timeline"][1]["starting"] == [1] and r["timeline"][2]["ending"] == [1]


def test_restoring_a_failed_node_is_an_improvement_not_an_impact():
    nodes = [node(1, "A", state="failed"), node(2, "B")]
    r = run(nodes, [edge(1, 1, 2)], [ev(1, "recovery", 1)])
    m = r["metrics"]
    assert m["impact_score"] == 0 and m["improved_nodes"] == 2 and m["affected_nodes"] == 0
    assert "no_baseline_service" in codes(r)


def test_invalid_scenarios_are_refused():
    nodes, edges = CHAIN
    with pytest.raises(SimulationInputError, match="no events"):
        run(nodes, edges, [])
    with pytest.raises(SimulationInputError):
        run([node(1, "Hall", "building")], [], [ev(1, "road_closure", 1)])
    with pytest.raises(SimulationInputError, match="does not exist"):
        run(nodes, [edge(9, 1, 99)], [ev(1, "failure", 1)])


def test_non_convergence_is_a_visible_warning():
    nodes = [node(1, "A"), node(2, "B")]
    edges = [edge(1, 1, 2, "partial", 0.5), edge(2, 2, 1, "partial", 0.5)]
    r = run(nodes, edges, [ev(1, "capacity_reduction", 1, reduction_pct=50)], max_iterations=1)
    assert r["solver"]["converged"] is False and "not_converged" in codes(r)


def test_a_baseline_shortfall_is_reported():
    nodes = [node(1, "Supply", "electricity", 50), node(2, "C1", "building", demands={"electricity": 100})]
    r = run(nodes, [edge(1, 1, 2)], [ev(1, "failure", 1)])
    assert "baseline_shortfall" in codes(r)


def test_the_work_limit_stops_a_run():
    with pytest.raises(SimulationLimitError):
        run(*CHAIN, [ev(1, "failure", 1)], max_work=1)