from app.seed.campus import CAMPUS_EDGES, CAMPUS_NODES


def make_env(client, name="Test Env"):
    r = client.post("/api/environments", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()


def add_node(client, env_id, name, **kw):
    r = client.post(f"/api/environments/{env_id}/nodes", json={"name": name, **kw})
    assert r.status_code == 201, r.text
    return r.json()


def add_edge(client, env_id, s, d, **kw):
    return client.post(f"/api/environments/{env_id}/edges",
                       json={"source_id": s, "destination_id": d, **kw})


def test_create_and_reopen_environment(client):
    env = make_env(client)
    a = add_node(client, env["id"], "A", category="electricity")
    b = add_node(client, env["id"], "B", category="building")
    assert add_edge(client, env["id"], a["id"], b["id"]).status_code == 201
    detail = client.get(f"/api/environments/{env['id']}").json()
    assert [n["name"] for n in detail["nodes"]] == ["A", "B"]
    assert len(detail["edges"]) == 1 and detail["edges"][0]["relationship_type"] == "required"


def test_duplicate_node_name_rejected(client):
    env = make_env(client)
    add_node(client, env["id"], "Power")
    r = client.post(f"/api/environments/{env['id']}/nodes", json={"name": "power"})
    assert r.status_code == 409


def test_invalid_node_values_rejected(client):
    env = make_env(client)
    url = f"/api/environments/{env['id']}/nodes"
    assert client.post(url, json={"name": "X", "importance": 1.5}).status_code == 422
    assert client.post(url, json={"name": "X", "capacity": -1}).status_code == 422
    assert client.post(url, json={"name": "X", "category": "banana"}).status_code == 422
    assert client.post(url, json={"name": "   "}).status_code == 422


def test_self_loop_rejected(client):
    env = make_env(client)
    a = add_node(client, env["id"], "A")
    assert add_edge(client, env["id"], a["id"], a["id"]).status_code == 422


def test_edge_to_node_in_other_environment_rejected(client):
    e1, e2 = make_env(client, "One"), make_env(client, "Two")
    a = add_node(client, e1["id"], "A")
    b = add_node(client, e2["id"], "B")
    assert add_edge(client, e1["id"], a["id"], b["id"]).status_code == 422


def test_duplicate_edge_rejected(client):
    env = make_env(client)
    a, b = add_node(client, env["id"], "A"), add_node(client, env["id"], "B")
    assert add_edge(client, env["id"], a["id"], b["id"]).status_code == 201
    assert add_edge(client, env["id"], a["id"], b["id"]).status_code == 409


def test_patch_node_state_and_position(client):
    env = make_env(client)
    a = add_node(client, env["id"], "A")
    r = client.patch(f"/api/nodes/{a['id']}", json={"state": "failed", "pos_x": 120, "pos_y": 40})
    assert r.status_code == 200 and r.json()["state"] == "failed" and r.json()["pos_x"] == 120


def test_delete_node_removes_its_edges(client):
    env = make_env(client)
    a, b = add_node(client, env["id"], "A"), add_node(client, env["id"], "B")
    add_edge(client, env["id"], a["id"], b["id"])
    assert client.delete(f"/api/nodes/{a['id']}").status_code == 204
    detail = client.get(f"/api/environments/{env['id']}").json()
    assert len(detail["nodes"]) == 1 and detail["edges"] == []


def test_duplicate_environment_copies_graph(client):
    env = make_env(client)
    a, b = add_node(client, env["id"], "A"), add_node(client, env["id"], "B")
    add_edge(client, env["id"], a["id"], b["id"], relationship_type="partial", strength=0.4)
    dup = client.post(f"/api/environments/{env['id']}/duplicate").json()
    assert dup["id"] != env["id"] and dup["node_count"] == 2 and dup["edge_count"] == 1
    copy_detail = client.get(f"/api/environments/{dup['id']}").json()
    assert copy_detail["edges"][0]["strength"] == 0.4
    assert {n["id"] for n in copy_detail["nodes"]}.isdisjoint({a["id"], b["id"]})


def test_delete_environment_cascades(client):
    env = make_env(client)
    a = add_node(client, env["id"], "A")
    assert client.delete(f"/api/environments/{env['id']}").status_code == 204
    assert client.get(f"/api/environments/{env['id']}").status_code == 404
    assert client.patch(f"/api/nodes/{a['id']}", json={"state": "failed"}).status_code == 404


def test_validate_endpoint_reports_isolated_node(client):
    env = make_env(client)
    add_node(client, env["id"], "Alone")
    r = client.post(f"/api/environments/{env['id']}/validate").json()
    assert r["valid"] and any(i["code"] == "isolated_node" for i in r["issues"])


def test_campus_demo_loads_and_validates(client):
    r = client.post("/api/demo/campus")
    assert r.status_code == 201
    env = r.json()
    assert env["is_demo"] and env["node_count"] == len(CAMPUS_NODES) and env["edge_count"] == len(CAMPUS_EDGES)
    report = client.post(f"/api/environments/{env['id']}/validate").json()
    assert report["valid"] and report["error_count"] == 0
    assert client.post("/api/demo/campus").status_code == 409