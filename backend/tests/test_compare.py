"""Comparison engine on a graph small enough to check by hand.

Grid (electricity, importance 1) -> Hall (building, importance 0.5, needs 50 kW). The Grid fails at t=0.
Intervention: add 'Gen' (electricity, capacity 60, importance 0.5) and a backup edge Gen -> Hall.
  baseline run : loss = Grid 1.0 + Hall 0.5 x 1 = 1.5 of 1.5                      -> score 1.0
  strength 1.0 : Hall keeps 100%. Shared-node loss 1.0 / 1.5 = 0.6667; raw score 1.0 / (1 + .5 + .5) = 0.5
  strength 0.5 : Hall keeps 50%.  Shared-node loss (1.0 + .5 x .5) / 1.5 = 0.8333
"""
import copy

import pytest

from app.engine.compare import ComparisonError, compare
from app.engine.modifications import apply_modifications, describe_modifications, fingerprint
from app.engine.simulate import run_simulation


def node(i, name, cat, cap=0.0, imp=0.5, demands=None):
    return {"id": i, "name": name, "category": cat, "state": "operational", "capacity": cap, "demand": 0.0,
            "importance": imp, "pos_x": i * 100, "pos_y": 0, "meta": {"unit": "kW", "demands": demands or {}}}


NODES = [node(1, "Grid", "electricity", 100, 1.0), node(2, "Hall", "building", 0, 0.5, {"electricity": 50})]
EDGES = [{"id": 10, "source_id": 1, "destination_id": 2, "relationship_type": "required", "strength": 1.0, "capacity": None}]
FAIL = [{"id": 1, "event_type": "failure", "target_node_id": 1, "params": {}, "start_time": 0.0, "duration": None}]
GEN = {"type": "add_node", "key": "gen", "name": "Gen", "category": "electricity", "capacity": 60, "importance": 0.5, "unit": "kW"}


def sim(sid, mods=(), nodes=NODES, edges=EDGES, events=FAIL, env=1, model="1.0.0", version=1, name="Grid failure"):
    snap = {"environment": {"id": env, "name": "E"}, "scenario": {"id": 1, "name": name, "version": version, "assumptions": []},
            "nodes": copy.deepcopy(nodes), "edges": copy.deepcopy(edges), "events": events,
            "base_hash": fingerprint(nodes, edges)}
    if mods:
        snap["nodes"], snap["edges"] = apply_modifications(nodes, edges, list(mods))
        snap.update(base_nodes=copy.deepcopy(nodes), base_edges=copy.deepcopy(edges), modifications=list(mods),
                    modification_labels=describe_modifications(list(mods), nodes, edges))
    result = run_simulation(snap["nodes"], snap["edges"], events)
    return {"id": sid, "scenario_id": 1, "scenario_name": name, "scenario_version": version, "environment_id": env,
            "environment_name": "E", "model_version": model, "started_at": "2026-11-09T00:00:00", "snapshot": snap,
            "result": result}


def backup(strength):
    return [GEN, {"type": "add_edge", "source": "gen", "destination": 2, "relationship_type": "backup", "strength": strength}]


def row(c, key):
    return next(r for r in c["metrics"] if r["key"] == key)


def codes(c):
    return {w["code"] for w in c["warnings"]}


def test_baseline_versus_a_full_backup_hand_checked():
    c = compare([sim(1), sim(2, backup(1.0), version=2)])
    assert row(c, "impact_score")["values"] == [1.0, 0.5]            # raw: 1.0 / (1 + .5 + .5)
    assert row(c, "adjusted_score")["values"] == pytest.approx([1.0, 2 / 3], abs=1e-6)
    assert row(c, "weighted_loss")["values"] == [1.5, 1.0]
    assert row(c, "total_nodes")["values"] == [2, 3] and c["common_node_count"] == 2
    assert row(c, "adjusted_score")["best"] == [1] and row(c, "total_nodes")["best"] == []
    assert row(c, "affected_nodes")["values"] == [2, 1]


def test_a_half_strength_backup_helps_less_than_a_full_one():
    c = compare([sim(1), sim(2, backup(1.0), version=2), sim(3, backup(0.5), version=3)])
    assert row(c, "adjusted_score")["values"] == pytest.approx([1.0, 2 / 3, 5 / 6], abs=1e-6)
    assert row(c, "adjusted_score")["best"] == [1]
    hall = next(n for n in c["nodes"] if n["name"] == "Hall")
    assert hall["levels"] == pytest.approx([0.0, 1.0, 0.5]) and hall["in_all"] and hall["spread"] == 1.0
    assert c["nodes"][0]["name"] == "Hall"                              # biggest spread first
    gen = next(n for n in c["nodes"] if n["name"] == "Gen")
    assert gen["levels"][0] is None and not gen["in_all"]


def test_added_nodes_trigger_the_dilution_warning():
    c = compare([sim(1), sim(2, backup(1.0), version=2)])
    assert "different_node_sets" in codes(c) and "environment_edited" not in codes(c)
    assert "different_node_sets" not in codes(compare([sim(1), sim(2, version=2)]))


def test_the_explanation_names_where_the_runs_diverge_and_the_modification_responsible():
    c = compare([sim(1), sim(2, backup(1.0), version=2)])
    e = c["explanations"][0]
    assert e["simulation_id"] == 2 and e["reference_id"] == 1
    assert "lower modelled impact score" in e["headline"] and "0.667 vs 1.000" in e["headline"]
    text = " ".join(e["details"])
    assert "Add backup connection 'Gen' -> 'Hall'" in text
    assert "'Hall': 0% -> 100% (+100 pts)" in text
    assert "first differ at 'Hall' (0% in Grid failure v1 (#1) vs 100% in Grid failure v2 (#2))" in text
    assert "directly affected by the modification" in text


def test_identical_runs_have_identical_scores_and_no_best_marker():
    c = compare([sim(1), sim(2, version=2)])
    assert row(c, "adjusted_score")["best"] == [] and "same modelled impact score" in c["explanations"][0]["headline"]


def test_an_edited_environment_is_flagged_with_the_change():
    edited = copy.deepcopy(NODES)
    edited[0]["capacity"] = 400
    c = compare([sim(1), sim(2, nodes=edited, version=2)])
    w = next(w for w in c["warnings"] if w["code"] == "environment_edited")
    assert "'Grid' capacity: 100 -> 400" in w["message"] and w["level"] == "warning"


def test_different_events_and_peaks_are_noted():
    later = [dict(FAIL[0], start_time=3.0)]
    c = compare([sim(1), sim(2, events=later, version=2)])
    assert {"different_events", "different_peak_times"} <= codes(c)


def test_incompatible_selections_are_refused():
    with pytest.raises(ComparisonError, match="Select between 2 and 6"):
        compare([sim(1)])
    with pytest.raises(ComparisonError, match="Select between 2 and 6"):
        compare([sim(i, version=i) for i in range(1, 8)])
    with pytest.raises(ComparisonError, match="only be selected once"):
        compare([sim(1), sim(1)])
    with pytest.raises(ComparisonError, match="different environments"):
        compare([sim(1), sim(2, env=2)])
    with pytest.raises(ComparisonError, match="different model versions"):
        compare([sim(1), sim(2, model="0.9.0")])


def test_unserved_demand_and_category_rows():
    c = compare([sim(1), sim(2, backup(1.0), version=2)])
    u = next(r for r in c["unserved"] if r["key"].startswith("electricity"))
    assert u["baseline"] == [0, 0] and u["scenario"][0] == 50           # Grid delivers 0 of the 50 kW Hall requests
    assert {r["category"] for r in c["categories"]} == {"building", "electricity"}


def test_comparison_is_deterministic():
    import json
    sims = lambda: [sim(1), sim(2, backup(1.0), version=2)]  # noqa: E731
    assert json.dumps(compare(sims()), sort_keys=True) == json.dumps(compare(sims()), sort_keys=True)