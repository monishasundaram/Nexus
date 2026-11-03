import pytest

from app.engine.propagation import Network, SimulationLimitError


def node(i, cat="generic", cap=0.0, demands=None, demand=0.0):
    meta = {"demands": demands} if demands is not None else {}
    return {"id": i, "name": f"N{i}", "category": cat, "state": "operational",
            "capacity": cap, "demand": demand, "importance": 0.5, "meta": meta}


def edge(i, s, d, rel="required", strength=1.0):
    return {"id": i, "source_id": s, "destination_id": d, "relationship_type": rel,
            "strength": strength, "capacity": None}


def solve(nodes, edges, own=None, **kw):
    net = Network(nodes, edges)
    factors = {n["id"]: 1.0 for n in nodes}
    factors.update(own or {})
    vals, sweeps, ok = net.solve(factors, **kw)
    return net, vals, sweeps, ok


def lv(vals):
    return {i: v.lvl for i, v in vals.items()}


CHAIN = ([node(1), node(2), node(3)], [edge(1, 1, 2), edge(2, 2, 3)])


# ---------- required / partial / backup ----------
def test_required_chain_failure_reaches_the_end():
    _, vals, _, ok = solve(*CHAIN, own={1: 0.0})
    assert ok and lv(vals) == {1: 0.0, 2: 0.0, 3: 0.0}


def test_required_chain_passes_a_reduction_on():
    _, vals, *_ = solve(*CHAIN, own={1: 0.5})
    assert lv(vals) == {1: 0.5, 2: 0.5, 3: 0.5}


def test_an_acyclic_graph_converges_in_two_sweeps():
    _, _, sweeps, ok = solve(*CHAIN, own={1: 0.0})
    assert ok and sweeps == 2


def test_the_lowest_required_supplier_limits_the_node():
    _, vals, *_ = solve([node(1), node(2), node(3)], [edge(1, 1, 3), edge(2, 2, 3)], own={1: 0.6, 2: 0.8})
    assert vals[3].lvl == pytest.approx(0.6)


def test_strength_scales_how_much_loss_is_passed_on():
    _, vals, *_ = solve([node(1), node(2)], [edge(1, 1, 2, strength=0.5)], own={1: 0.0})
    assert vals[2].lvl == pytest.approx(0.5)  # 1 - 0.5 * (1 - 0)


def test_partial_losses_multiply():
    nodes = [node(1), node(2), node(3)]
    edges = [edge(1, 1, 3, "partial", 0.5), edge(2, 2, 3, "partial", 0.5)]
    assert solve(nodes, edges, own={1: 0.0})[1][3].lvl == pytest.approx(0.5)
    assert solve(nodes, edges, own={1: 0.0, 2: 0.0})[1][3].lvl == pytest.approx(0.25)


def test_a_backup_replaces_a_lost_primary():
    nodes = [node(1), node(2), node(3)]
    edges = [edge(1, 1, 3), edge(2, 2, 3, "backup", 0.7)]

    def level(own):
        return solve(nodes, edges, own=own)[1][3].lvl

    assert level({}) == pytest.approx(1.0)
    assert level({1: 0.0}) == pytest.approx(0.7)
    assert level({1: 0.5}) == pytest.approx(1.0)   # 0.5 + 0.7 is capped at 1
    assert level({1: 0.0, 2: 0.0}) == pytest.approx(0.0)


def test_a_nodes_own_state_caps_its_level():
    _, vals, *_ = solve([node(1), node(2)], [edge(1, 1, 2)], own={2: 0.5})
    assert vals[2].lvl == pytest.approx(0.5)


# ---------- quantities ----------
POWER = (
    [node(1, "electricity", 100), node(2, "electricity", 40), node(3, "electricity", 100),
     node(4, "building", demands={"electricity": 30}), node(5, "building", demands={"electricity": 30})],
    [edge(1, 1, 3), edge(2, 2, 3, "backup", 0.5), edge(3, 3, 4), edge(4, 3, 5)],
)


def test_a_backup_delivers_only_what_its_capacity_allows():
    net, vals, *_ = solve(*POWER)
    assert net.demand[3] == 60 and vals[3].lvl == pytest.approx(1.0)
    _, vals, *_ = solve(*POWER, own={1: 0.0})
    assert vals[3].out == pytest.approx(20)        # 40 kW generator x 0.5 strength
    assert vals[3].lvl == pytest.approx(1 / 3)     # 20 of 60 demanded
    assert vals[4].lvl == pytest.approx(1 / 3) and vals[5].lvl == pytest.approx(1 / 3)


def test_a_bigger_backup_helps():
    nodes, edges = POWER
    bigger = [dict(n, capacity=80) if n["id"] == 2 else n for n in nodes]
    _, vals, *_ = solve(bigger, edges, own={1: 0.0})
    assert vals[3].lvl == pytest.approx(2 / 3)     # 80 x 0.5 = 40 of 60


def test_a_backup_covers_a_partial_shortfall():
    _, vals, *_ = solve(*POWER, own={1: 0.5})
    assert vals[3].out == pytest.approx(70)        # 50 from the grid + 20 from the generator
    assert vals[3].lvl == pytest.approx(1.0)


def test_consumers_share_a_shortfall_proportionally():
    nodes = [node(1, "electricity", 100), node(2, "building", demands={"electricity": 50}),
             node(3, "building", demands={"electricity": 50})]
    _, vals, *_ = solve(nodes, [edge(1, 1, 2), edge(2, 1, 3)], own={1: 0.5})
    assert [vals[i].lvl for i in (1, 2, 3)] == pytest.approx([0.5, 0.5, 0.5])


def test_spare_capacity_absorbs_a_reduction():
    nodes = [node(1, "electricity", 100), node(2, "building", demands={"electricity": 30})]
    _, vals, *_ = solve(nodes, [edge(1, 1, 2)], own={1: 0.8})
    assert vals[1].a == pytest.approx(0.8)
    assert vals[1].lvl == pytest.approx(1.0) and vals[2].lvl == pytest.approx(1.0)


WATER = (
    [node(1, "water", 500), node(2, "water", 500), node(3, "water", 400),
     node(4, "building", demands={"water": 330})],
    [edge(1, 1, 2), edge(2, 2, 3), edge(3, 3, 4)],
)


def test_quantities_flow_along_a_resource_chain():
    _, vals, *_ = solve(*WATER, own={1: 0.5})
    assert vals[2].out == pytest.approx(250) and vals[3].out == pytest.approx(250)
    assert vals[3].lvl == pytest.approx(250 / 330) and vals[4].lvl == pytest.approx(250 / 330)


def test_downstream_spare_capacity_hides_a_small_upstream_loss():
    _, vals, *_ = solve(*WATER, own={1: 0.9})
    assert vals[3].out == pytest.approx(400)       # 450 arrives, the tank passes at most 400
    assert vals[4].lvl == pytest.approx(1.0)


# ---------- cycles and safety limits ----------
CYCLE = ([node(1), node(2)], [edge(1, 1, 2, "partial", 0.5), edge(2, 2, 1, "partial", 0.5)])


def test_a_cycle_fails_when_a_member_fails():
    nodes, edges = [node(1), node(2)], [edge(1, 1, 2), edge(2, 2, 1)]
    assert lv(solve(nodes, edges)[1]) == {1: 1.0, 2: 1.0}
    _, vals, _, ok = solve(nodes, edges, own={1: 0.0})
    assert ok and lv(vals) == {1: 0.0, 2: 0.0}


def test_a_partial_cycle_converges_to_its_fixed_point():
    # a1 = 0.5 * (1 - 0.5 * (1 - a2)),  a2 = 1 - 0.5 * (1 - a1)  ->  a1 = 3/7, a2 = 5/7
    _, vals, sweeps, ok = solve(*CYCLE, own={1: 0.5})
    assert ok and sweeps > 2
    assert vals[1].a == pytest.approx(3 / 7, abs=1e-6)
    assert vals[2].a == pytest.approx(5 / 7, abs=1e-6)


def test_not_converging_is_reported_not_hidden():
    _, _, sweeps, ok = solve(*CYCLE, own={1: 0.5}, max_iterations=1)
    assert not ok and sweeps == 1


def test_the_work_limit_stops_a_runaway_simulation():
    net = Network(*CHAIN, max_work=1)
    with pytest.raises(SimulationLimitError):
        net.solve({1: 1.0, 2: 1.0, 3: 1.0})


# ---------- demand rules ----------
def test_declared_demand_beats_the_plain_demand_field():
    nodes = [node(1, "electricity", 100), node(2, "building", demands={"electricity": 40}, demand=999)]
    assert Network(nodes, [edge(1, 1, 2)]).demand[1] == 40


def test_plain_demand_is_used_when_there_is_one_resource_supplier():
    net = Network([node(1, "electricity", 100), node(2, "building", demand=30)], [edge(1, 1, 2)])
    assert net.demand[1] == 30 and net.notes == []


def test_ambiguous_plain_demand_is_ignored_with_a_note():
    nodes = [node(1, "electricity", 100), node(2, "water", 100), node(3, "building", demand=30)]
    net = Network(nodes, [edge(1, 1, 3), edge(2, 2, 3)])
    assert net.demand[1] == 0 and net.demand[2] == 0
    assert [n["code"] for n in net.notes] == ["ambiguous_demand"]


def test_two_edges_between_the_same_pair_count_demand_once():
    nodes = [node(1, "electricity", 100), node(2, "building", demands={"electricity": 40})]
    net = Network(nodes, [edge(1, 1, 2), edge(2, 1, 2, "partial", 0.5)])
    assert net.demand[1] == 40