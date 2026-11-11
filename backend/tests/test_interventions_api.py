import pytest

from app.database import get_db
from app.main import app
from app.models import Simulation


def campus(client):
    env = client.post("/api/demo/campus").json()
    made = {s["name"]: s for s in client.post(f"/api/environments/{env['id']}/demo-scenarios").json()}
    detail = client.get(f"/api/environments/{env['id']}").json()
    return env, made, {n["name"]: n for n in detail["nodes"]}


def simulate(client, scenario):
    r = client.post(f"/api/scenarios/{scenario['id']}/simulate")
    assert r.status_code == 201, r.text
    return r.json()


def variant(client, base, mods, finalize=True):
    v = client.post(f"/api/scenarios/{base['id']}/new-version").json()
    r = client.put(f"/api/scenarios/{v['id']}/modifications", json={"modifications": mods})
    assert r.status_code == 200, r.text
    if finalize:
        assert client.post(f"/api/scenarios/{v['id']}/finalize").status_code == 200
    return r.json()


def metric(c, key):
    return next(m for m in c["metrics"] if m["key"] == key)["values"]


# ---------- modifications on scenarios ----------
def test_modifications_are_saved_labelled_and_copied_by_new_versions_and_duplicates(client):
    _, sc, nodes = campus(client)
    base = sc["Primary electricity supply failure"]
    v2 = variant(client, base, [{"type": "set_capacity", "node_id": nodes["Backup Diesel Generator"]["id"], "capacity": 1000}], finalize=False)
    assert v2["version"] == 2 and v2["modification_labels"] == ["Set capacity of 'Backup Diesel Generator' to 1000 kW (was 400)"]
    assert client.get(f"/api/scenarios/{base['id']}").json()["modifications"] == []     # v1 untouched
    client.post(f"/api/scenarios/{v2['id']}/finalize")
    v3 = client.post(f"/api/scenarios/{v2['id']}/new-version").json()
    dup = client.post(f"/api/scenarios/{v2['id']}/duplicate").json()
    assert v3["modifications"] == v2["modifications"] and dup["modifications"] == v2["modifications"]


def test_final_versions_and_invalid_modifications_are_refused(client):
    _, sc, nodes = campus(client)
    base = sc["Primary electricity supply failure"]              # sample scenarios are final
    url = f"/api/scenarios/{base['id']}/modifications"
    ok = {"type": "set_capacity", "node_id": nodes["Backup Diesel Generator"]["id"], "capacity": 1000}
    assert client.put(url, json={"modifications": [ok]}).status_code == 409
    v2 = client.post(f"/api/scenarios/{base['id']}/new-version").json()
    url = f"/api/scenarios/{v2['id']}/modifications"
    bad = [
        {"type": "set_capacity", "node_id": 999999, "capacity": 5},
        {"type": "set_capacity", "node_id": 1, "capacity": -5},
        {"type": "reduce_demand", "node_id": 1, "reduce_pct": 0},
        {"type": "teleport", "node_id": 1},
        {"type": "set_capacity", "node_id": 1, "capacity": 5, "extra": True},
        {"type": "set_edge", "edge_id": 1},
        {"type": "add_node", "key": "bad key!", "name": "X", "category": "generic"},
        {"type": "add_edge", "source": "ghost", "destination": 1},
    ]
    for m in bad:
        assert client.put(url, json={"modifications": [m]}).status_code == 422, m
    assert client.put(url, json={"modifications": [ok] * 31}).status_code == 422
    assert client.get(f"/api/scenarios/{v2['id']}").json()["modifications"] == []       # nothing half-saved


def test_validation_reports_modification_problems_and_blocks_finalizing(client):
    env, sc, nodes = campus(client)
    base = sc["Primary electricity supply failure"]
    gen = nodes["Backup Diesel Generator"]
    v2 = variant(client, base, [{"type": "set_capacity", "node_id": gen["id"], "capacity": 400}], finalize=False)
    report = client.post(f"/api/scenarios/{v2['id']}/validate").json()
    assert report["valid"] and "mod_no_change" in {i["code"] for i in report["issues"]}
    assert client.delete(f"/api/nodes/{gen['id']}").status_code == 204
    report = client.post(f"/api/scenarios/{v2['id']}/validate").json()
    assert not report["valid"] and "mod_missing_node" in {i["code"] for i in report["issues"]}
    assert client.post(f"/api/scenarios/{v2['id']}/finalize").status_code == 422


# ---------- simulating a variant ----------
def test_a_variant_runs_on_a_modified_copy_and_the_environment_stays_unchanged(client):
    env, sc, nodes = campus(client)
    before = client.get(f"/api/environments/{env['id']}").json()
    v2 = variant(client, sc["Primary electricity supply failure"], [
        {"type": "add_node", "key": "solar", "name": "Solar Array", "category": "electricity", "capacity": 500, "importance": 0.6, "unit": "kW"},
        {"type": "add_edge", "source": "solar", "destination": nodes["Main Substation"]["id"], "relationship_type": "backup", "strength": 0.8}])
    sim = simulate(client, v2)
    assert sim["result"]["metrics"]["total_nodes"] == 22
    # substation inflow = 0 (grid) + 400 x 0.8 (diesel) + 500 x 0.8 (solar) = 720 kW of the 790 kW requested
    assert sim["result"]["unserved"]["electricity (kW)"]["scenario"] == 70
    snap = client.get(f"/api/simulations/{sim['id']}/snapshot").json()
    assert len(snap["nodes"]) == 22 and len(snap["base_nodes"]) == 21 and len(snap["modifications"]) == 2
    solar = next(n for n in snap["nodes"] if n["name"] == "Solar Array")
    assert solar["added"] and solar["id"] == max(n["id"] for n in before["nodes"]) + 1
    assert snap["modification_labels"][1] == "Add backup connection 'Solar Array' -> 'Main Substation' (strength 0.8)"
    assert client.get(f"/api/environments/{env['id']}").json() == before          # baseline environment untouched


def test_a_modification_that_became_invalid_stops_the_simulation_and_saves_nothing(client):
    env, sc, nodes = campus(client)
    gen = nodes["Backup Diesel Generator"]
    v2 = variant(client, sc["Primary electricity supply failure"], [{"type": "set_capacity", "node_id": gen["id"], "capacity": 1000}])
    client.delete(f"/api/nodes/{gen['id']}")
    r = client.post(f"/api/scenarios/{v2['id']}/simulate")
    assert r.status_code == 422 and "cannot be simulated" in r.json()["detail"]
    assert client.get("/api/simulations").json() == []


# ---------- comparing ----------
def test_comparing_a_baseline_with_an_intervention(client):
    _, sc, nodes = campus(client)
    base = sc["Primary electricity supply failure"]
    sim1 = simulate(client, base)
    v2 = variant(client, base, [{"type": "set_capacity", "node_id": nodes["Backup Diesel Generator"]["id"], "capacity": 1000}])
    sim2 = simulate(client, v2)
    r = client.post("/api/comparisons", json={"simulation_ids": [sim1["id"], sim2["id"]]})
    assert r.status_code == 201
    c = r.json()
    assert metric(c, "impact_score") == [pytest.approx(0.45522), pytest.approx(0.064935)]
    assert metric(c, "affected_nodes") == [14, 1] and metric(c, "degraded_nodes") == [13, 0]
    assert [x for x in c["unserved"] if x["key"] == "electricity (kW)"][0]["scenario"] == [470, 0]
    assert c["warnings"] == [] and c["common_node_count"] == 21 and c["reference_id"] == sim1["id"]
    assert c["simulations"][1]["modifications"] == ["Set capacity of 'Backup Diesel Generator' to 1000 kW (was 400)"]
    text = " ".join(c["explanations"][0]["details"])
    assert "first differ at 'Main Substation' (41% in" in text and "directly affected by the modification" in text
    assert "No single metric" in c["notes"][0]


def test_added_nodes_dilute_the_raw_score_and_the_adjusted_score_corrects_it(client):
    _, sc, nodes = campus(client)
    base = sc["Primary electricity supply failure"]
    sim1 = simulate(client, base)
    v2 = variant(client, base, [
        {"type": "add_node", "key": "solar", "name": "Solar Array", "category": "electricity", "capacity": 500, "importance": 0.6, "unit": "kW"},
        {"type": "add_edge", "source": "solar", "destination": nodes["Main Substation"]["id"], "relationship_type": "backup", "strength": 0.8}])
    c = client.post("/api/comparisons", json={"simulation_ids": [sim1["id"], simulate(client, v2)["id"]]}).json()
    raw, adj = metric(c, "impact_score")[1], metric(c, "adjusted_score")[1]
    assert raw == pytest.approx(0.122578) and adj == pytest.approx(0.127354) and adj > raw
    assert metric(c, "total_nodes") == [21, 22] and c["common_node_count"] == 21
    assert "different_node_sets" in {w["code"] for w in c["warnings"]}


def test_an_environment_edit_between_runs_is_flagged(client):
    _, sc, nodes = campus(client)
    base = sc["Primary electricity supply failure"]
    sim1 = simulate(client, base)
    client.patch(f"/api/nodes/{nodes['Backup Diesel Generator']['id']}", json={"capacity": 900})
    sim2 = simulate(client, base)
    c = client.post("/api/comparisons", json={"simulation_ids": [sim1["id"], sim2["id"]]}).json()
    w = next(w for w in c["warnings"] if w["code"] == "environment_edited")
    assert "'Backup Diesel Generator' capacity: 400 -> 900" in w["message"]


def test_incompatible_comparisons_are_refused(client):
    env, sc, _ = campus(client)
    sim1 = simulate(client, sc["Primary electricity supply failure"])
    other = client.post("/api/environments/%d/duplicate" % env["id"]).json()
    other_sc = client.post(f"/api/environments/{other['id']}/demo-scenarios").json()[0]
    sim2 = simulate(client, other_sc)
    post = lambda ids: client.post("/api/comparisons", json={"simulation_ids": ids})  # noqa: E731
    assert post([sim1["id"]]).status_code == 422                               # needs two
    assert post([sim1["id"], sim1["id"]]).status_code == 422                   # same one twice
    r = post([sim1["id"], sim2["id"]])
    assert r.status_code == 422 and "different environments" in r.json()["detail"]
    assert post([sim1["id"], 9999]).status_code == 404
    sim3 = simulate(client, sc["Water supply capacity reduced by 50%"])
    db = next(app.dependency_overrides[get_db]())
    db.get(Simulation, sim3["id"]).model_version = "0.9.0"
    db.commit()
    db.close()
    r = post([sim1["id"], sim3["id"]])
    assert r.status_code == 422 and "different model versions" in r.json()["detail"]
    assert client.get("/api/comparisons").json() == []                          # refusals store nothing


def test_comparisons_are_saved_recomputed_deduplicated_and_survive_deletes_gracefully(client):
    _, sc, _ = campus(client)
    a, b = simulate(client, sc["Primary electricity supply failure"]), simulate(client, sc["Critical campus road closure"])
    ids = [a["id"], b["id"]]
    first = client.post("/api/comparisons", json={"simulation_ids": ids}).json()
    again = client.post("/api/comparisons", json={"simulation_ids": ids}).json()
    assert first["id"] == again["id"] and len(client.get("/api/comparisons").json()) == 1
    swapped = client.post("/api/comparisons", json={"simulation_ids": ids[::-1]}).json()
    assert swapped["id"] != first["id"] and swapped["reference_id"] == b["id"]   # order decides the reference
    reopened = client.get(f"/api/comparisons/{first['id']}").json()
    strip = lambda d: {k: v for k, v in d.items() if k != "created_at"}  # noqa: E731
    assert strip(reopened) == strip(first)
    listing = client.get("/api/comparisons").json()
    assert listing[0]["labels"][0].startswith("Critical campus road closure") or listing[0]["labels"][0].startswith("Primary")
    assert client.get("/api/dashboard").json()["recent_comparisons"][0]["available"] is True
    client.delete(f"/api/simulations/{b['id']}")
    assert client.get(f"/api/comparisons/{first['id']}").status_code == 404
    gone = next(c for c in client.get("/api/comparisons").json() if c["id"] == first["id"])
    assert gone["available"] is False and any("deleted simulation" in x for x in gone["labels"])
    assert client.delete(f"/api/comparisons/{first['id']}").status_code == 204
    assert client.get(f"/api/comparisons/{first['id']}").status_code == 404


def test_dilution_does_not_apply_without_added_nodes_and_comparing_different_disruptions_is_noted(client):
    _, sc, _ = campus(client)
    a, b = simulate(client, sc["Primary electricity supply failure"]), simulate(client, sc["Water supply capacity reduced by 50%"])
    c = client.post("/api/comparisons", json={"simulation_ids": [a["id"], b["id"]]}).json()
    codes = {w["code"] for w in c["warnings"]}
    assert "different_events" in codes and "different_node_sets" not in codes
    assert metric(c, "impact_score") == metric(c, "adjusted_score")