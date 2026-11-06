"""Runs the real engine on the NEXUS Campus sample data. Expected values are checked by hand in comments."""
import json

import pytest

from app.engine.scenario_validation import validate_scenario
from app.engine.simulate import run_simulation
from app.engine.validation import validate_graph
from app.seed.plain import campus_graph, sample_events
from app.seed.scenarios import SAMPLE_SCENARIOS

PRIMARY, WATER, ROAD, COMBINED = SAMPLE_SCENARIOS


def run(spec, tweak=None, events=None):
    ids, nodes, edges = campus_graph()
    if tweak:
        tweak(nodes, edges)
    return run_simulation(nodes, edges, events or sample_events(spec, ids))


def node(r, name):
    return next(n for n in r["node_results"] if n["name"] == name)


def trace(r, name):
    return next(t for t in r["traces"] if t["node_name"] == name)


def codes(r):
    return {w["code"] for w in r["warnings"]}


def affected_names(r):
    return {n["name"] for n in r["node_results"] if n["trend"] == "worse"}


# ---------- the sample data itself ----------
def test_campus_graph_and_sample_scenarios_are_valid():
    ids, nodes, edges = campus_graph()
    assert (len(nodes), len(edges)) == (21, 50)
    report = validate_graph(nodes, edges)
    assert report["valid"] and report["warning_count"] == 0
    for spec in SAMPLE_SCENARIOS:
        slim = [{k: n[k] for k in ("id", "name", "category", "state", "capacity")} for n in nodes]
        assert validate_scenario(slim, sample_events(spec, ids))["valid"]


def test_the_campus_baseline_is_fully_served():
    # demand on the substation = 60 + 30 + 20 + 680 (all buildings) = 790 of 1000 kW + 320 kW backup headroom
    # demand on the tank = 330 of 400 kL/day
    r = run(PRIMARY)
    assert r["capacity"][0]["baseline_unserved"] == 0
    assert all(row["baseline_level"] == 1 for row in r["capacity"])
    assert all(n["baseline_level"] == 1 for n in r["node_results"])
    assert "baseline_shortfall" not in codes(r)


# ---------- scenario 1: primary electricity failure ----------
def test_primary_failure_counts_and_hand_checked_values():
    r = run(PRIMARY)
    m = r["metrics"]
    assert (m["total_nodes"], m["affected_nodes"], m["direct_nodes"], m["indirect_nodes"]) == (21, 14, 1, 13)
    assert (m["failed_nodes"], m["degraded_nodes"]) == (1, 13)
    assert m["impact_score"] == pytest.approx(0.455, abs=0.001)

    # inflow to the substation = 0 (grid) + 400 kW generator x 0.8 = 320 kW, against 790 kW requested
    sub = node(r, "Main Substation")
    assert sub["output"] == pytest.approx(320) and sub["level"] == pytest.approx(320 / 790)
    assert r["unserved"]["electricity (kW)"] == {"baseline": 0, "scenario": pytest.approx(470)}

    # the pump house runs at 320/790 of 500 kL/day, so the tank passes on 500 x 320/790 against 330 requested
    pump_out = 500 * 320 / 790
    assert node(r, "Overhead Water Tank")["output"] == pytest.approx(pump_out)
    assert r["unserved"]["water (kL/day)"]["scenario"] == pytest.approx(330 - pump_out)


def test_primary_failure_leaves_roads_alone_and_explains_the_chain():
    r = run(PRIMARY)
    assert node(r, "Central Avenue")["impact"] == "none"
    assert node(r, "Campus Shuttle Route")["impact"] == "none"
    t = trace(r, "Science Block")
    assert t["path_names"] == ["Primary Grid Supply", "Main Substation", "Science Block"]
    assert t["impact"] == "indirect" and t["event_ids"] == [1]
    assert "Origin: Infrastructure failure on 'Primary Grid Supply'" in t["explanation"]
    assert trace(r, "Primary Grid Supply")["impact"] == "direct"


def test_without_the_diesel_backup_the_campus_loses_far_more():
    def cut_backup(nodes, edges):
        edges[:] = [e for e in edges if not (e["relationship_type"] == "backup" and e["id"] == 2)]

    base, bare = run(PRIMARY), run(PRIMARY, cut_backup)
    assert bare["metrics"]["impact_score"] > base["metrics"]["impact_score"]
    assert bare["metrics"]["failed_nodes"] == 13
    assert bare["unserved"]["electricity (kW)"]["scenario"] == pytest.approx(790)


def test_a_bigger_generator_is_a_measurable_improvement():
    def bigger(nodes, edges):
        next(n for n in nodes if n["name"] == "Backup Diesel Generator")["capacity"] = 1000

    base, better = run(PRIMARY), run(PRIMARY, bigger)
    # 1000 kW x 0.8 = 800 kW >= 790 kW requested: electricity is fully served again
    assert better["unserved"]["electricity (kW)"]["scenario"] == 0
    assert better["metrics"]["impact_score"] < base["metrics"]["impact_score"]
    assert better["metrics"]["affected_nodes"] == 1  # only the grid itself is lost


# ---------- scenario 2: water -50% ----------
def test_water_reduction_hand_checked_values():
    r = run(WATER)
    m = r["metrics"]
    assert (m["affected_nodes"], m["direct_nodes"], m["indirect_nodes"]) == (11, 1, 10)
    assert (m["failed_nodes"], m["degraded_nodes"]) == (0, 11)
    assert m["affected_categories"] == {"building": 8, "water": 3}
    # 250 kL/day leaves the main, the pump house passes it on, the tank requests 330
    assert node(r, "Water Pump House")["level"] == pytest.approx(0.5)
    assert node(r, "Overhead Water Tank")["level"] == pytest.approx(250 / 330)
    assert r["unserved"]["water (kL/day)"]["scenario"] == pytest.approx(80)
    assert r["unserved"]["electricity (kW)"]["scenario"] == 0
    assert node(r, "Main Substation")["impact"] == "none"


# ---------- scenario 3: road closure ----------
def test_road_closure_hand_checked_values():
    r = run(ROAD)
    m = r["metrics"]
    assert (m["affected_nodes"], m["direct_nodes"], m["indirect_nodes"]) == (9, 1, 8)
    assert (m["failed_nodes"], m["degraded_nodes"]) == (1, 8)
    assert node(r, "Central Avenue")["state"] == "failed"
    # the shuttle loses its required road but the east ring road backs it up at strength 0.7
    assert node(r, "Campus Shuttle Route")["level"] == pytest.approx(0.7)
    # Lecture Hall: Central Avenue partial 0.6 -> 0.4, shuttle partial 0.3 -> 1 - 0.3 x 0.3 = 0.91; 0.4 x 0.91
    assert node(r, "Lecture Hall Complex")["level"] == pytest.approx(0.364)
    assert r["unserved"]["electricity (kW)"]["scenario"] == 0


# ---------- scenario 4: combined ----------
def test_combined_disruption_is_worse_than_each_part():
    parts = [run(s) for s in (PRIMARY, WATER, ROAD)]
    both = run(COMBINED)
    m = both["metrics"]
    assert (m["affected_nodes"], m["direct_nodes"], m["indirect_nodes"]) == (17, 3, 14)
    assert m["failed_nodes"] == 2
    assert m["impact_score"] > max(p["metrics"]["impact_score"] for p in parts)
    assert affected_names(both) >= set().union(*(affected_names(p) for p in parts))
    assert "simultaneous_disruptions" in codes(both)


def test_sample_scenarios_raise_no_unexpected_warnings():
    for spec in (PRIMARY, WATER, ROAD):
        assert run(spec)["warnings"] == []


# ---------- reproducibility and time ----------
def test_campus_runs_are_reproducible():
    a, b = run(COMBINED), run(COMBINED)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_grid_failure_with_a_timed_recovery():
    ids, _, _ = campus_graph()
    grid = ids["Primary Grid Supply"]
    events = [
        {"id": 1, "event_type": "failure", "target_node_id": grid, "params": {}, "start_time": 2.0, "duration": None},
        {"id": 2, "event_type": "recovery", "target_node_id": grid, "params": {}, "start_time": 8.0, "duration": None},
    ]
    r = run(PRIMARY, events=events)
    m = r["metrics"]
    assert [s["time"] for s in r["timeline"]] == [0.0, 2.0, 8.0]
    assert [s["impact_score"] for s in r["timeline"]] == [0.0, m["impact_score"], 0.0]
    assert (m["peak_time"], m["recovered_at"], m["final_score"]) == (2.0, 8.0, 0.0)
    assert m["impact_hours"] == pytest.approx(6 * m["impact_score"], abs=1e-4)