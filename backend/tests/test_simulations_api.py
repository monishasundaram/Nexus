def campus(client):
    env = client.post("/api/demo/campus").json()
    made = client.post(f"/api/environments/{env['id']}/demo-scenarios").json()
    return env, {s["name"]: s for s in made}


def run(client, scenario):
    r = client.post(f"/api/scenarios/{scenario['id']}/simulate")
    assert r.status_code == 201, r.text
    return r.json()


def test_a_draft_scenario_cannot_be_simulated(client):
    env, _ = campus(client)
    node = client.get(f"/api/environments/{env['id']}").json()["nodes"][0]
    draft = client.post(f"/api/environments/{env['id']}/scenarios", json={
        "name": "Draft", "events": [{"event_type": "failure", "target_node_id": node["id"]}]}).json()
    r = client.post(f"/api/scenarios/{draft['id']}/simulate")
    assert r.status_code == 409 and "Finalize" in r.json()["detail"]
    assert client.get("/api/simulations").json() == []


def test_run_and_reopen_a_simulation(client):
    env, sc = campus(client)
    s = sc["Primary electricity supply failure"]
    sim = run(client, s)
    assert sim["status"] == "completed" and sim["scenario_id"] == s["id"] and sim["scenario_version"] == 1
    assert sim["environment_name"] == "NEXUS Campus" and sim["node_count"] == 21 and sim["edge_count"] == 50
    res = sim["result"]
    m = res["metrics"]
    assert (m["affected_nodes"], m["direct_nodes"], m["indirect_nodes"]) == (14, 1, 13)
    assert len(res["node_results"]) == 21 and len(res["traces"]) == 14
    assert res["unserved"]["electricity (kW)"]["scenario"] == 470
    assert res["formula"] and res["limitations"] and res["timeline"][0]["time"] == 0
    assert any(a.startswith("Scenario: ") for a in res["assumptions"])
    again = client.get(f"/api/simulations/{sim['id']}").json()
    assert again == sim  # what was stored is exactly what was returned


def test_the_baseline_environment_is_not_changed_by_simulating(client):
    env, sc = campus(client)
    before = client.get(f"/api/environments/{env['id']}").json()
    for s in sc.values():
        run(client, s)
    assert client.get(f"/api/environments/{env['id']}").json() == before


def test_repeating_a_run_gives_identical_results(client):
    _, sc = campus(client)
    a, b = run(client, sc["Combined disruption"]), run(client, sc["Combined disruption"])
    assert a["id"] != b["id"]
    for key in ("metrics", "node_results", "traces", "capacity", "timeline", "warnings"):
        assert a["result"][key] == b["result"][key]


def test_the_snapshot_keeps_old_results_reproducible(client):
    env, sc = campus(client)
    s = sc["Primary electricity supply failure"]
    old = run(client, s)
    nodes = {n["name"]: n for n in client.get(f"/api/environments/{env['id']}").json()["nodes"]}
    gen = nodes["Backup Diesel Generator"]
    assert client.patch(f"/api/nodes/{gen['id']}", json={"capacity": 1000}).status_code == 200
    new = run(client, s)
    assert new["result"]["unserved"]["electricity (kW)"]["scenario"] == 0
    assert new["result"]["metrics"]["impact_score"] < old["result"]["metrics"]["impact_score"]
    assert client.get(f"/api/simulations/{old['id']}").json()["result"]["metrics"] == old["result"]["metrics"]
    snap_old = client.get(f"/api/simulations/{old['id']}/snapshot").json()
    snap_new = client.get(f"/api/simulations/{new['id']}/snapshot").json()
    cap = lambda snap: next(n["capacity"] for n in snap["nodes"] if n["name"] == "Backup Diesel Generator")
    assert (cap(snap_old), cap(snap_new)) == (400, 1000)
    assert snap_old["scenario"]["version"] == 1 and len(snap_old["events"]) == 1


def test_simulations_stay_linked_to_the_exact_scenario_version(client):
    _, sc = campus(client)
    v1 = sc["Water supply capacity reduced by 50%"]
    sim1 = run(client, v1)
    v2 = client.post(f"/api/scenarios/{v1['id']}/new-version").json()
    ev = v2["events"][0]
    body = {"name": v2["name"], "description": v2["description"], "assumptions": v2["assumptions"],
            "events": [{"event_type": "capacity_reduction", "target_node_id": ev["target_node_id"],
                        "params": {"reduction_pct": 20}}]}
    assert client.put(f"/api/scenarios/{v2['id']}", json=body).status_code == 200
    assert client.post(f"/api/scenarios/{v2['id']}/finalize").status_code == 200
    sim2 = run(client, v2)
    assert (sim1["scenario_version"], sim2["scenario_version"]) == (1, 2)
    assert sim2["result"]["metrics"]["impact_score"] < sim1["result"]["metrics"]["impact_score"]
    only_v2 = client.get("/api/simulations", params={"scenario_id": v2["id"]}).json()
    assert [s["id"] for s in only_v2] == [sim2["id"]]


def test_listing_simulations_and_the_dashboard(client):
    _, sc = campus(client)
    assert client.get("/api/dashboard").json()["completed_simulations"] == 0
    a = run(client, sc["Primary electricity supply failure"])
    b = run(client, sc["Critical campus road closure"])
    rows = client.get("/api/simulations").json()
    assert [r["id"] for r in rows] == [b["id"], a["id"]]  # newest first
    assert rows[0]["metrics"]["affected_nodes"] == 9 and rows[1]["metrics"]["affected_nodes"] == 14
    assert client.get("/api/dashboard").json()["completed_simulations"] == 2
    scn = client.get(f"/api/scenarios/{sc['Critical campus road closure']['id']}").json()
    assert scn["simulation_count"] == 1


def test_a_scenario_whose_target_was_deleted_is_refused_and_nothing_is_saved(client):
    env, sc = campus(client)
    s = sc["Critical campus road closure"]
    avenue = next(n for n in client.get(f"/api/environments/{env['id']}").json()["nodes"]
                  if n["name"] == "Central Avenue")
    assert client.delete(f"/api/nodes/{avenue['id']}").status_code == 204
    r = client.post(f"/api/scenarios/{s['id']}/simulate")
    assert r.status_code == 422 and "cannot be simulated" in r.json()["detail"]
    assert client.get("/api/simulations").json() == []


def test_delete_a_simulation(client):
    _, sc = campus(client)
    sim = run(client, sc["Primary electricity supply failure"])
    assert client.delete(f"/api/simulations/{sim['id']}").status_code == 204
    assert client.get(f"/api/simulations/{sim['id']}").status_code == 404
    assert client.get(f"/api/simulations/{sim['id']}/snapshot").status_code == 404


def test_unknown_ids_return_404(client):
    assert client.post("/api/scenarios/999/simulate").status_code == 404
    assert client.get("/api/simulations/999").status_code == 404
    assert client.delete("/api/simulations/999").status_code == 404


def test_deleting_a_scenario_also_removes_its_simulations(client):
    _, sc = campus(client)
    s = sc["Primary electricity supply failure"]
    sim = run(client, s)
    assert client.delete(f"/api/scenarios/{s['id']}").status_code == 409
    assert client.delete(f"/api/scenarios/{s['id']}?force=true").status_code == 204
    assert client.get(f"/api/simulations/{sim['id']}").status_code == 404