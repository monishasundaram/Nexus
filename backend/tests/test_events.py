from app.engine.events import check_event_shape
from app.engine.scenario_validation import validate_scenario


def node(i, name, cat="generic", state="operational", cap=100):
    return dict(id=i, name=name, category=cat, state=state, capacity=cap)


def ev(i, kind, target, start=0.0, duration=None, **params):
    return dict(id=i, event_type=kind, target_node_id=target, params=params,
                start_time=start, duration=duration)


def codes(report, level=None):
    return {i["code"] for i in report["issues"] if level in (None, i["level"])}


# ---------- shape rules ----------
def test_failure_has_no_params():
    assert check_event_shape("failure", {}, None) == []
    assert check_event_shape("failure", {}, 5) == []


def test_failure_rejects_extra_params():
    assert check_event_shape("failure", {"reduction_pct": 10}, None)


def test_percentage_bounds():
    def ok(v):
        return check_event_shape("capacity_reduction", {"reduction_pct": v}, None) == []
    assert ok(50) and ok(100) and ok(0.5)
    assert not ok(0) and not ok(-5) and not ok(100.1)


def test_percentage_must_be_a_number():
    assert check_event_shape("capacity_reduction", {}, None)
    assert check_event_shape("capacity_reduction", {"reduction_pct": "50"}, None)
    assert check_event_shape("capacity_reduction", {"reduction_pct": True}, None)


def test_duration_rules():
    assert check_event_shape("maintenance", {}, None)
    assert check_event_shape("maintenance", {}, 4) == []
    assert check_event_shape("recovery", {}, 4)
    assert check_event_shape("recovery", {}, None) == []


def test_unknown_event_type():
    assert check_event_shape("meteor", {}, None)


# ---------- scenario validation ----------
def test_simple_failure_is_valid():
    r = validate_scenario([node(1, "Grid", "electricity")], [ev(1, "failure", 1)])
    assert r["valid"] and r["issues"] == [] and r["stats"]["event_count"] == 1


def test_empty_scenario_is_an_error():
    assert "no_events" in codes(validate_scenario([node(1, "Grid")], []), "error")


def test_too_many_events():
    r = validate_scenario([node(1, "Grid")], [ev(i, "failure", 1, start=i) for i in range(1, 6)], max_events=3)
    assert "too_many_events" in codes(r, "error")


def test_missing_target():
    r = validate_scenario([node(1, "Grid")], [ev(1, "failure", 99), ev(2, "failure", None)])
    assert not r["valid"] and "missing_target" in codes(r, "error")


def test_wrong_target_category():
    nodes = [node(1, "Hall", "building")]
    r = validate_scenario(nodes, [ev(1, "road_closure", 1), ev(2, "resource_shortage", 1, shortage_pct=20)])
    assert "wrong_target_category" in codes(r, "error")
    assert len([i for i in r["issues"] if i["code"] == "wrong_target_category"]) == 2


def test_invalid_shape_reported():
    r = validate_scenario([node(1, "Grid")], [ev(1, "capacity_reduction", 1)])
    assert "invalid_event" in codes(r, "error")


def test_zero_capacity_warning():
    r = validate_scenario([node(1, "Hall", "building", cap=0)], [ev(1, "capacity_reduction", 1, reduction_pct=50)])
    assert r["valid"] and "zero_capacity" in codes(r, "warning")


def test_already_down_info():
    r = validate_scenario([node(1, "Grid", state="failed")], [ev(1, "failure", 1)])
    assert "already_down" in codes(r, "info")


def test_duplicate_event_warning():
    r = validate_scenario([node(1, "Grid")], [ev(1, "failure", 1), ev(2, "failure", 1)])
    assert "duplicate_event" in codes(r, "warning")


def test_overlapping_events_warning():
    r = validate_scenario([node(1, "Grid")],
                          [ev(1, "failure", 1, 0, 5), ev(2, "capacity_reduction", 1, 3, 5, reduction_pct=50)])
    assert "overlapping_events" in codes(r, "warning")


def test_back_to_back_events_do_not_overlap():
    r = validate_scenario([node(1, "Grid")], [ev(1, "failure", 1, 0, 5), ev(2, "failure", 1, 5, 5)])
    assert "overlapping_events" not in codes(r)


def test_recovery_without_disruption_warning():
    r = validate_scenario([node(1, "Grid")], [ev(1, "recovery", 1, 2)])
    assert "recovery_without_disruption" in codes(r, "warning")


def test_recovery_after_open_failure_is_fine():
    r = validate_scenario([node(1, "Grid")], [ev(1, "failure", 1, 0), ev(2, "recovery", 1, 5)])
    assert "recovery_without_disruption" not in codes(r)


def test_recovery_of_a_baseline_failed_node_is_fine():
    r = validate_scenario([node(1, "Grid", state="failed")], [ev(1, "recovery", 1, 0)])
    assert r["valid"] and "recovery_without_disruption" not in codes(r)


def test_recovery_after_disruption_already_ended_warns():
    r = validate_scenario([node(1, "Grid")], [ev(1, "failure", 1, 0, 2), ev(2, "recovery", 1, 5)])
    assert "recovery_without_disruption" in codes(r, "warning")


def test_simultaneous_disruptions_are_flagged():
    r = validate_scenario([node(1, "A"), node(2, "B")], [ev(1, "failure", 1), ev(2, "failure", 2)])
    assert r["valid"] and "simultaneous_disruptions" in codes(r, "info")
    assert "overlapping_events" not in codes(r)