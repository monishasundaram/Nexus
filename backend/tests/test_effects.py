import pytest

from app.engine.effects import change_times, own_factors


def node(i, state="operational"):
    return {"id": i, "name": f"N{i}", "category": "generic", "state": state}


def ev(i, kind, target=1, start=0.0, duration=None, **params):
    return {"id": i, "event_type": kind, "target_node_id": target, "params": params,
            "start_time": start, "duration": duration}


def factor(events, t, state="operational"):
    return own_factors({1: node(1, state)}, events, t)[1][0]


def test_baseline_states():
    nodes = {i: node(i, s) for i, s in enumerate(["operational", "degraded", "failed", "maintenance"], start=1)}
    got = {i: f for i, (f, _) in own_factors(nodes, [], 0).items()}
    assert got == {1: 1.0, 2: 0.5, 3: 0.0, 4: 0.0}


def test_failure_starts_when_the_event_starts():
    e = [ev(1, "failure", start=2)]
    assert factor(e, 1.9) == 1.0
    assert factor(e, 2) == 0.0


def test_duration_is_half_open():
    e = [ev(1, "failure", start=1, duration=2)]
    assert factor(e, 2.9) == 0.0
    assert factor(e, 3) == 1.0


def test_reductions_multiply():
    e = [ev(1, "capacity_reduction", reduction_pct=50), ev(2, "resource_shortage", shortage_pct=20)]
    assert factor(e, 0) == pytest.approx(0.4)


def test_outage_dominates_reductions():
    e = [ev(1, "capacity_reduction", reduction_pct=50), ev(2, "road_closure")]
    assert factor(e, 0) == 0.0


def test_recovery_ends_earlier_effects():
    e = [ev(1, "failure"), ev(2, "recovery", start=5)]
    assert factor(e, 4) == 0.0
    assert factor(e, 5) == 1.0


def test_new_disruption_after_recovery_applies():
    e = [ev(1, "failure"), ev(2, "recovery", start=5), ev(3, "failure", start=8)]
    assert [factor(e, t) for t in (4, 6, 9)] == [0.0, 1.0, 0.0]


def test_recovery_restores_a_baseline_failed_or_degraded_node():
    assert factor([ev(1, "recovery")], 0, state="failed") == 1.0
    assert factor([ev(1, "recovery")], 0, state="degraded") == 1.0


def test_recovery_clears_reductions_too():
    e = [ev(1, "capacity_reduction", reduction_pct=50), ev(2, "recovery", start=3)]
    assert factor(e, 2) == 0.5 and factor(e, 3) == 1.0


def test_same_start_events_apply_in_id_order():
    assert factor([ev(1, "failure", start=2), ev(2, "recovery", start=2)], 2) == 1.0
    assert factor([ev(1, "recovery", start=2), ev(2, "failure", start=2)], 2) == 0.0


def test_active_event_ids_are_reported():
    nodes = {1: node(1)}
    assert own_factors(nodes, [ev(7, "failure")], 0)[1][1] == [7]
    assert own_factors(nodes, [ev(7, "failure", duration=1)], 5)[1][1] == []


def test_change_times():
    assert change_times([]) == [0.0]
    events = [ev(1, "failure", start=2, duration=3), ev(2, "recovery", start=10)]
    assert change_times(events) == [0.0, 2.0, 5.0, 10.0]