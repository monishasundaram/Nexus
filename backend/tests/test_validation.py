from app.engine.validation import validate_graph


def node(i, name, **kw):
    base = dict(id=i, name=name, category="generic", state="operational",
                capacity=0, demand=0, importance=0.5)
    return {**base, **kw}


def edge(i, s, d, rel="required", strength=1.0):
    return dict(id=i, source_id=s, destination_id=d, relationship_type=rel,
                strength=strength, capacity=None)


def codes(report, level=None):
    return {i["code"] for i in report["issues"] if level in (None, i["level"])}


def test_simple_chain_is_valid():
    r = validate_graph([node(1, "A"), node(2, "B"), node(3, "C")], [edge(1, 1, 2), edge(2, 2, 3)])
    assert r["valid"] and r["issues"] == []
    assert r["stats"]["node_count"] == 3 and r["stats"]["has_cycles"] is False


def test_dangling_edge_is_error():
    r = validate_graph([node(1, "A")], [edge(1, 1, 99)])
    assert not r["valid"] and "dangling_edge" in codes(r, "error")


def test_self_loop_and_duplicate_edge_are_errors():
    r = validate_graph([node(1, "A"), node(2, "B")], [edge(1, 1, 1), edge(2, 1, 2), edge(3, 1, 2)])
    assert {"self_loop", "duplicate_edge"} <= codes(r, "error")


def test_duplicate_names_are_case_insensitive():
    r = validate_graph([node(1, "Power"), node(2, "power")], [edge(1, 1, 2)])
    assert "duplicate_name" in codes(r, "error")


def test_cycle_is_a_warning_not_an_error():
    r = validate_graph([node(1, "A"), node(2, "B")], [edge(1, 1, 2), edge(2, 2, 1)])
    assert r["valid"] and "cycle" in codes(r, "warning") and r["stats"]["has_cycles"]


def test_isolated_node_warning():
    r = validate_graph([node(1, "A"), node(2, "B"), node(3, "Lonely")], [edge(1, 1, 2)])
    assert "isolated_node" in codes(r, "warning")


def test_backup_without_primary_warning():
    r = validate_graph([node(1, "A"), node(2, "B")], [edge(1, 1, 2, rel="backup")])
    assert "backup_without_primary" in codes(r, "warning")


def test_backup_with_primary_is_fine():
    r = validate_graph([node(1, "A"), node(2, "B"), node(3, "C")],
                       [edge(1, 1, 3), edge(2, 2, 3, rel="backup")])
    assert "backup_without_primary" not in codes(r)


def test_size_limit_is_enforced():
    r = validate_graph([node(i, f"N{i}") for i in range(1, 6)], [], max_nodes=3)
    assert "too_many_nodes" in codes(r, "error")


def test_demand_over_capacity_warning():
    r = validate_graph([node(1, "A", capacity=10, demand=20), node(2, "B")], [edge(1, 1, 2)])
    assert "demand_exceeds_capacity" in codes(r, "warning")


def test_building_without_supplier_warning():
    r = validate_graph([node(1, "Hall", category="building"), node(2, "Road")], [edge(1, 1, 2)])
    assert "unsupplied_building" in codes(r, "warning")