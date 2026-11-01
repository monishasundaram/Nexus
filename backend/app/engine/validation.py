"""Graph validation. Pure Python: no web framework or database imports."""
from collections import Counter, defaultdict

import networkx as nx

from ..config import MAX_EDGES, MAX_NODES


def _issue(level, code, message, node_ids=(), edge_ids=()):
    return {"level": level, "code": code, "message": message,
            "node_ids": list(node_ids), "edge_ids": list(edge_ids)}


def validate_graph(nodes: list[dict], edges: list[dict],
                   max_nodes: int = MAX_NODES, max_edges: int = MAX_EDGES) -> dict:
    issues: list[dict] = []
    name_of = {n["id"]: n["name"] for n in nodes}
    category = {n["id"]: n["category"] for n in nodes}

    if len(nodes) > max_nodes:
        issues.append(_issue("error", "too_many_nodes",
                             f"Graph has {len(nodes)} nodes; the limit is {max_nodes}."))
    if len(edges) > max_edges:
        issues.append(_issue("error", "too_many_edges",
                             f"Graph has {len(edges)} edges; the limit is {max_edges}."))

    # --- nodes ---
    names = defaultdict(list)
    for n in nodes:
        names[n["name"].strip().lower()].append(n["id"])
    for key, group in names.items():
        if len(group) > 1:
            issues.append(_issue("error", "duplicate_name",
                                 f"The name '{key}' is used by {len(group)} nodes.", group))

    for n in nodes:
        nid, label = n["id"], n["name"]
        if n["capacity"] < 0 or n["demand"] < 0:
            issues.append(_issue("error", "negative_value",
                                 f"'{label}' has a negative capacity or demand.", [nid]))
        if not 0 <= n["importance"] <= 1:
            issues.append(_issue("error", "bad_importance",
                                 f"'{label}' has an importance outside 0-1.", [nid]))
        if n["capacity"] > 0 and n["demand"] > n["capacity"]:
            issues.append(_issue("warning", "demand_exceeds_capacity",
                                 f"'{label}' has demand ({n['demand']}) above its capacity ({n['capacity']}).", [nid]))
        if n["state"] != "operational":
            issues.append(_issue("info", "baseline_not_operational",
                                 f"'{label}' is '{n['state']}' in the baseline, so every simulation starts from that state.", [nid]))

    # --- edges ---
    seen: dict[tuple, int] = {}
    good: list[dict] = []
    for e in edges:
        s, d, t = e["source_id"], e["destination_id"], e["relationship_type"]
        if s not in name_of or d not in name_of:
            issues.append(_issue("error", "dangling_edge",
                                 f"Edge {e['id']} points to a node that does not exist.", edge_ids=[e["id"]]))
            continue
        if s == d:
            issues.append(_issue("error", "self_loop",
                                 f"'{name_of[s]}' depends on itself.", [s], [e["id"]]))
            continue
        if (s, d, t) in seen:
            issues.append(_issue("error", "duplicate_edge",
                                 f"Duplicate '{t}' connection from '{name_of[s]}' to '{name_of[d]}'.",
                                 [s, d], [seen[(s, d, t)], e["id"]]))
            continue
        seen[(s, d, t)] = e["id"]
        if not 0 <= e["strength"] <= 1:
            issues.append(_issue("error", "bad_strength",
                                 f"Edge {e['id']} has a dependency strength outside 0-1.", edge_ids=[e["id"]]))
        good.append(e)

    # --- structure ---
    g = nx.DiGraph()
    g.add_nodes_from(name_of)
    g.add_edges_from((e["source_id"], e["destination_id"]) for e in good)

    isolated = set(nx.isolates(g))
    for nid in isolated:
        issues.append(_issue("warning", "isolated_node",
                             f"'{name_of[nid]}' has no connections, so no scenario can affect it or spread from it.", [nid]))

    has_cycles = False
    for group in nx.strongly_connected_components(g):
        if len(group) > 1:
            has_cycles = True
            members = ", ".join(sorted(name_of[i] for i in group))
            issues.append(_issue("warning", "cycle",
                                 f"Circular dependency among: {members}. The engine resolves cycles with a bounded iteration.",
                                 group))

    incoming = defaultdict(list)
    for e in good:
        incoming[e["destination_id"]].append(e)
    for nid, es in incoming.items():
        if all(e["relationship_type"] == "backup" for e in es):
            issues.append(_issue("warning", "backup_without_primary",
                                 f"'{name_of[nid]}' only has backup suppliers and no primary supplier.", [nid]))

    for nid in name_of:
        if category[nid] == "building" and nid not in isolated and g.in_degree(nid) == 0:
            issues.append(_issue("warning", "unsupplied_building",
                                 f"Building '{name_of[nid]}' has no suppliers, so upstream failures can never reach it.", [nid]))

    rank = {"error": 0, "warning": 1, "info": 2}
    issues.sort(key=lambda i: rank[i["level"]])
    errors = sum(1 for i in issues if i["level"] == "error")
    return {
        "valid": errors == 0,
        "error_count": errors,
        "warning_count": sum(1 for i in issues if i["level"] == "warning"),
        "issues": issues,
        "stats": {"node_count": len(nodes), "edge_count": len(edges),
                  "categories": dict(Counter(category.values())), "has_cycles": has_cycles},
    }