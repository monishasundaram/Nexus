from app.database import get_db
from app.main import app
from app.models import Simulation


def setup(client, name="Env"):
    env = client.post("/api/environments", json={"name": name}).json()

    def mk(n, category, **kw):
        r = client.post(f"/api/environments/{env['id']}/nodes", json={"name": n, "category": category, **kw})
        assert r.status_code == 201, r.text
        return r.json()

    return env, mk("Grid", "electricity", capacity=100), mk("Road", "road", capacity=50), mk("Hall", "building", demand=10)


def body(name="S1", events=None, **kw):
    return {"name": name, "events": events or [], **kw}


def event(kind, node, start=0, duration=None, **params):
    return {"event_type": kind, "target_node_id": node["id"], "params": params,
            "start_time": start, "duration": duration}


def make(client, env, name="S1", events=None):
    r = client.post(f"/api/environments/{env['id']}/scenarios", json=body(name, events))
    assert r.status_code == 201, r.text
    return r.json()


def codes(report):
    return {i["code"] for i in report["issues"]}


def test_event_types_endpoint(client):
    types = client.get("/api/event-types").json()
    assert len(types) == 6 and {t["type"] for t in types} >= {"failure", "recovery", "road_closure"}


def test_create_and_reopen_scenario(client):
    env, grid, *_ = setup(client)
    s = make(client, env, events=[event("capacity_reduction", grid, start=2, reduction_pct=50),
                                  event("failure", grid)])
    assert s["version"] == 1 and s["status"] == "draft"
    got = client.get(f"/api/scenarios/{s['id']}").json()
    assert [e["event_type"] for e in got["events"]] == ["failure", "capacity_reduction"]  # sorted by start time
    assert got["events"][1]["params"] == {"reduction_pct": 50}
    assert got["environment_name"] == "Env"


def test_invalid_events_rejected(client):
    env, grid, *_ = setup(client)
    url = f"/api/environments/{env['id']}/scenarios"
    bad = [
        event("capacity_reduction", grid),
        event("capacity_reduction", grid, reduction_pct=150),
        event("maintenance", grid),
        event("recovery", grid, duration=3),
        event("failure", grid, start=-1),
        {**event("failure", grid), "event_type": "meteor"},
    ]
    for ev in bad:
        assert client.post(url, json=body("X", [ev])).status_code == 422
    assert client.post(url, json=body("Big", [event("failure", grid)] * 51)).status_code == 422


def test_targets_must_belong_to_the_environment(client):
    env, grid, *_ = setup(client)
    _, other, *_ = setup(client, "Other")
    url = f"/api/environments/{env['id']}/scenarios"
    assert client.post(url, json=body("A", [event("failure", other)])).status_code == 422
    assert client.post(url, json=body("B", [{**event("failure", grid), "target_node_id": 9999}])).status_code == 422
    assert client.get("/api/scenarios").json() == []  # nothing half-saved


def test_duplicate_scenario_name_rejected(client):
    env, *_ = setup(client)
    make(client, env, "S1")
    r = client.post(f"/api/environments/{env['id']}/scenarios", json=body("s1"))
    assert r.status_code == 409


def test_put_replaces_events_and_a_failed_put_changes_nothing(client):
    env, grid, road, _ = setup(client)
    s = make(client, env, events=[event("failure", grid)])
    url = f"/api/scenarios/{s['id']}"
    r = client.put(url, json=body("S1", [event("road_closure", road, start=3)], description="new"))
    assert r.status_code == 200 and r.json()["description"] == "new"
    assert [e["event_type"] for e in r.json()["events"]] == ["road_closure"]
    bad = client.put(url, json=body("S1", [{**event("failure", grid), "target_node_id": 9999}]))
    assert bad.status_code == 422
    assert [e["event_type"] for e in client.get(url).json()["events"]] == ["road_closure"]


def test_validate_endpoint(client):
    env, grid, road, _ = setup(client)
    empty = make(client, env, "Empty")
    assert "no_events" in codes(client.post(f"/api/scenarios/{empty['id']}/validate").json())
    wrong = make(client, env, "Wrong", [event("road_closure", grid)])
    r = client.post(f"/api/scenarios/{wrong['id']}/validate").json()
    assert not r["valid"] and "wrong_target_category" in codes(r)
    good = make(client, env, "Good", [event("road_closure", road)])
    assert client.post(f"/api/scenarios/{good['id']}/validate").json()["valid"]


def test_finalize_locks_the_scenario(client):
    env, grid, *_ = setup(client)
    bad = make(client, env, "Bad")
    assert client.post(f"/api/scenarios/{bad['id']}/finalize").status_code == 422
    good = make(client, env, "Good", [event("failure", grid)])
    fin = client.post(f"/api/scenarios/{good['id']}/finalize")
    assert fin.status_code == 200 and fin.json()["status"] == "final"
    assert client.put(f"/api/scenarios/{good['id']}", json=body("Good", [])).status_code == 409


def test_new_version_copies_and_keeps_the_original(client):
    env, grid, road, _ = setup(client)
    v1 = make(client, env, "S1", [event("failure", grid)])
    client.post(f"/api/scenarios/{v1['id']}/finalize")
    r = client.post(f"/api/scenarios/{v1['id']}/new-version")
    assert r.status_code == 201
    v2 = r.json()
    assert v2["version"] == 2 and v2["status"] == "draft" and v2["parent_id"] == v1["id"] and v2["name"] == "S1"
    assert len(v2["events"]) == 1 and v2["events"][0]["id"] != v1["events"][0]["id"]
    assert client.put(f"/api/scenarios/{v2['id']}", json=body("S1", [event("failure", road)])).status_code == 200
    assert client.get(f"/api/scenarios/{v1['id']}").json()["events"][0]["target_node_id"] == grid["id"]
    assert client.put(f"/api/scenarios/{v2['id']}", json=body("Renamed", [event("failure", road)])).status_code == 409
    assert client.post(f"/api/scenarios/{v1['id']}/new-version").json()["version"] == 3


def test_duplicate_scenario(client):
    env, grid, *_ = setup(client)
    s = make(client, env, "S1", [event("failure", grid)])
    client.post(f"/api/scenarios/{s['id']}/finalize")
    r1 = client.post(f"/api/scenarios/{s['id']}/duplicate")
    r2 = client.post(f"/api/scenarios/{s['id']}/duplicate")
    assert r1.status_code == 201
    d1, d2 = r1.json(), r2.json()
    assert d1["name"] == "S1 (copy)" and d2["name"] == "S1 (copy 2)"
    assert d1["version"] == 1 and d1["status"] == "draft" and len(d1["events"]) == 1


def test_archive_search_and_filters(client):
    env, grid, road, _ = setup(client)
    env2, g2, *_ = setup(client, "Other")
    a = make(client, env, "Alpha power", [event("failure", grid)])
    make(client, env, "Beta roads", [event("road_closure", road)])
    make(client, env2, "Gamma", [event("failure", g2)])

    def names(**params):
        return sorted(s["name"] for s in client.get("/api/scenarios", params=params).json())

    assert names() == ["Alpha power", "Beta roads", "Gamma"]
    assert names(q="ROAD") == ["Beta roads"]
    assert names(event_type="failure") == ["Alpha power", "Gamma"]
    assert names(environment_id=env["id"]) == ["Alpha power", "Beta roads"]
    client.post(f"/api/scenarios/{a['id']}/archive")
    assert names() == ["Beta roads", "Gamma"] and names(archived="true") == ["Alpha power"]
    client.post(f"/api/scenarios/{a['id']}/unarchive")
    assert len(names()) == 3


def test_delete_scenario_and_force_when_simulations_exist(client):
    env, grid, *_ = setup(client)
    s = make(client, env, "S1", [event("failure", grid)])
    db = next(app.dependency_overrides[get_db]())
    db.add(Simulation(scenario_id=s["id"], scenario_version=1, baseline_snapshot={}, model_version="1.0.0"))
    db.commit()
    db.close()
    assert client.get(f"/api/scenarios/{s['id']}").json()["simulation_count"] == 1
    assert client.delete(f"/api/scenarios/{s['id']}").status_code == 409
    assert client.delete(f"/api/scenarios/{s['id']}?force=true").status_code == 204
    assert client.get(f"/api/scenarios/{s['id']}").status_code == 404
    plain = make(client, env, "Plain")
    assert client.delete(f"/api/scenarios/{plain['id']}").status_code == 204


def test_deleting_a_node_makes_its_events_invalid(client):
    env, grid, *_ = setup(client)
    s = make(client, env, "S1", [event("failure", grid)])
    assert client.delete(f"/api/nodes/{grid['id']}").status_code == 204
    assert client.get(f"/api/scenarios/{s['id']}").json()["events"][0]["target_node_id"] is None
    r = client.post(f"/api/scenarios/{s['id']}/validate").json()
    assert not r["valid"] and "missing_target" in codes(r)


def test_sample_scenarios_on_campus(client):
    campus = client.post("/api/demo/campus").json()
    r = client.post(f"/api/environments/{campus['id']}/demo-scenarios")
    assert r.status_code == 201
    made = r.json()
    assert len(made) == 4 and all(s["status"] == "final" for s in made)
    names = {n["id"]: n["name"] for n in client.get(f"/api/environments/{campus['id']}").json()["nodes"]}
    primary = next(s for s in made if s["name"] == "Primary electricity supply failure")
    assert [names[e["target_node_id"]] for e in primary["events"]] == ["Primary Grid Supply"]
    assert len(next(s for s in made if s["name"] == "Combined disruption")["events"]) == 3
    assert client.post(f"/api/environments/{campus['id']}/demo-scenarios").status_code == 409


def test_sample_scenarios_need_the_campus_nodes(client):
    blank = client.post("/api/environments", json={"name": "Blank"}).json()
    assert client.post(f"/api/environments/{blank['id']}/demo-scenarios").status_code == 409
    campus = client.post("/api/demo/campus").json()
    copy = client.post(f"/api/environments/{campus['id']}/duplicate").json()
    r = client.post(f"/api/environments/{copy['id']}/demo-scenarios")
    assert r.status_code == 201
    copy_ids = {n["id"] for n in client.get(f"/api/environments/{copy['id']}").json()["nodes"]}
    assert all(e["target_node_id"] in copy_ids for s in r.json() for e in s["events"])