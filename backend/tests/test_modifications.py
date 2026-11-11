import copy

import pytest

from app.engine.modifications import (ModificationError, apply_modifications, check_modifications,
                                       describe_modifications, fingerprint, graph_diff)


def node(i, name, cat="generic", cap=0.0, demand=0.0, demands=None, x=0, y=0, unit=""):
    meta = {"unit": unit}
    if demands is not None:
        meta["demands"] = demands
    return {"id": i, "name": name, "category": cat, "state": "operational", "capacity": cap, "demand": demand,
            "importance": 0.5, "pos_x": x, "pos_y": y, "meta": meta}


def edge(i, s, d, rel="required", strength=1.0):
    return {"id": i, "source_id": s, "destination_id": d, "relationship_type": rel, "strength": strength, "capacity": None}


NODES = [node(1, "Grid", "electricity", 100, unit="kW", x=0, y=0), node(2, "Hall", "building", demands={"electricity": 50}, x=300, y=40)]
EDGES = [edge(10, 1, 2)]


def codes(issues, level=None):
    return {i["code"] for i in issues if level in (None, i["level"])}


def test_set_capacity_changes_a_copy_and_flags_the_node():
    before = copy.deepcopy((NODES, EDGES))
    n, e = apply_modifications(NODES, EDGES, [{"type": "set_capacity", "node_id": 1, "capacity": 250}])
    assert n[0]["capacity"] == 250 and n[0]["modified"] is True and "modified" not in n[1]
    assert (NODES, EDGES) == before          # the originals are never touched
    assert e == EDGES and e is not EDGES


def test_add_node_gets_the_next_id_a_position_below_the_graph_and_flags():
    mods = [{"type": "add_node", "key": "a", "name": "Solar", "category": "electricity", "capacity": 80, "importance": 0.4, "unit": "kW"},
            {"type": "add_node", "key": "b", "name": "Wind", "category": "electricity", "capacity": 20, "importance": 0.3}]
    n, _ = apply_modifications(NODES, EDGES, mods)
    a, b = n[2], n[3]
    assert (a["id"], b["id"]) == (3, 4) and a["added"] and a["state"] == "operational"
    assert (a["pos_x"], a["pos_y"]) == (0, 220) and (b["pos_x"], b["pos_y"]) == (240, 220)  # min x, max y + 180, 240 apart
    assert a["meta"]["unit"] == "kW" and a["meta"]["demands"] == {}


def test_add_edge_can_use_the_key_of_a_node_added_in_the_same_list():
    mods = [{"type": "add_edge", "source": "s", "destination": 2, "relationship_type": "backup", "strength": 0.7},
            {"type": "add_node", "key": "s", "name": "Solar", "category": "electricity", "capacity": 80, "importance": 0.4}]
    _, e = apply_modifications(NODES, EDGES, mods)    # order does not matter: new nodes are created first
    assert e[-1] == {"id": 11, "source_id": 3, "destination_id": 2, "relationship_type": "backup",
                     "strength": 0.7, "capacity": None, "added": True}


def test_set_edge_changes_strength_and_type():
    _, e = apply_modifications(NODES, EDGES, [{"type": "set_edge", "edge_id": 10, "strength": 0.4, "relationship_type": "partial"}])
    assert (e[0]["strength"], e[0]["relationship_type"], e[0]["modified"]) == (0.4, "partial", True)


def test_reduce_demand_scales_declared_demands_or_the_plain_field():
    n, _ = apply_modifications(NODES, EDGES, [{"type": "reduce_demand", "node_id": 2, "reduce_pct": 20}])
    assert n[1]["meta"]["demands"] == {"electricity": 40.0}
    plain = [node(1, "A", demand=100)]
    n, _ = apply_modifications(plain, [], [{"type": "reduce_demand", "node_id": 1, "reduce_pct": 25}])
    assert n[0]["demand"] == 75


def test_invalid_modifications_are_refused_with_readable_messages():
    bad = [
        [{"type": "set_capacity", "node_id": 99, "capacity": 5}],
        [{"type": "add_node", "key": "a", "name": "grid", "category": "generic"}],      # name taken, case-insensitive
        [{"type": "add_node", "key": "a", "name": "X", "category": "generic"}, {"type": "add_node", "key": "a", "name": "Y", "category": "generic"}],
        [{"type": "add_edge", "source": "nope", "destination": 2, "relationship_type": "required", "strength": 1}],
        [{"type": "add_edge", "source": 1, "destination": 1, "relationship_type": "required", "strength": 1}],
        [{"type": "add_edge", "source": 1, "destination": 2, "relationship_type": "required", "strength": 1}],   # exists
        [{"type": "set_edge", "edge_id": 77, "strength": 0.5}],
    ]
    for mods in bad:
        assert codes(check_modifications(NODES, EDGES, mods), "error"), mods
        with pytest.raises(ModificationError):
            apply_modifications(NODES, EDGES, mods)


def test_harmless_oddities_are_warnings_not_errors():
    issues = check_modifications(NODES, EDGES, [
        {"type": "set_capacity", "node_id": 1, "capacity": 100},                       # unchanged
        {"type": "reduce_demand", "node_id": 1, "reduce_pct": 10},                      # Grid has no demand
        {"type": "set_capacity", "node_id": 2, "capacity": 5}, {"type": "set_capacity", "node_id": 2, "capacity": 6},
    ])
    assert {"mod_no_change", "mod_no_demand", "mod_overrides"} <= codes(issues, "warning") and not codes(issues, "error")


def test_changing_an_edge_type_cannot_duplicate_an_existing_connection():
    edges = EDGES + [edge(11, 1, 2, "partial", 0.5)]
    assert "mod_duplicate_edge" in codes(check_modifications(NODES, edges, [{"type": "set_edge", "edge_id": 10, "relationship_type": "partial"}]), "error")


def test_the_modification_count_limit():
    mods = [{"type": "set_capacity", "node_id": 1, "capacity": float(i)} for i in range(31)]
    assert "mod_too_many" in codes(check_modifications(NODES, EDGES, mods), "error")


def test_labels_are_readable():
    mods = [{"type": "set_capacity", "node_id": 1, "capacity": 250}, {"type": "reduce_demand", "node_id": 2, "reduce_pct": 20},
            {"type": "add_node", "key": "s", "name": "Solar", "category": "electricity", "capacity": 80, "importance": 0.4, "unit": "kW"},
            {"type": "add_edge", "source": "s", "destination": 2, "relationship_type": "backup", "strength": 0.7},
            {"type": "set_edge", "edge_id": 10, "strength": 0.4}]
    assert describe_modifications(mods, NODES, EDGES) == [
        "Set capacity of 'Grid' to 250 kW (was 100)",
        "Reduce demand of 'Hall' by 20%",
        "Add electricity node 'Solar' (capacity 80 kW, importance 0.4)",
        "Add backup connection 'Solar' -> 'Hall' (strength 0.7)",
        "Change connection 'Grid' -> 'Hall': strength 1 -> 0.4"]


def test_fingerprint_ignores_positions_but_not_values():
    moved = copy.deepcopy(NODES)
    moved[0]["pos_x"] = 999
    assert fingerprint(moved, EDGES) == fingerprint(NODES, EDGES)
    bigger = copy.deepcopy(NODES)
    bigger[0]["capacity"] = 101
    assert fingerprint(bigger, EDGES) != fingerprint(NODES, EDGES)


def test_graph_diff_lists_what_changed():
    b = copy.deepcopy(NODES)
    b[0]["capacity"] = 400
    e = [dict(EDGES[0], strength=0.5)]
    assert graph_diff(NODES, EDGES, b, e) == ["'Grid' capacity: 100 -> 400", "connection #10 changed: required 1 -> required 0.5"]
    assert graph_diff(NODES, EDGES, NODES, EDGES) == []