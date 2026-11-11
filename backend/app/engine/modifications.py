"""Intervention modifications: changes applied to a COPY of the graph before simulating. Pure Python.

The stored environment is never touched. Added nodes get fresh ids above the existing ones, in list order.
Order of application: all add_node first, then every other modification in list order.
"""
import copy
import hashlib
import json

from ..config import MAX_EDGES, MAX_MODIFICATIONS, MAX_NODES


class ModificationError(ValueError):
    def __init__(self, messages: list[str]):
        super().__init__("; ".join(messages))
        self.messages = messages


def _issue(level, code, message, node_ids=()):
    return {"level": level, "code": code, "message": message, "node_ids": list(node_ids), "event_ids": []}


def _has_demand(node: dict) -> bool:
    declared = (node.get("meta") or {}).get("demands")
    if isinstance(declared, dict):
        return any(isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0 for v in declared.values())
    return node.get("demand", 0) > 0


def check_modifications(nodes: list[dict], edges: list[dict], mods: list[dict]) -> list[dict]:
    """Problems with a list of modifications against a graph. Pure: nothing is applied."""
    issues: list[dict] = []
    by_id = {n["id"]: n for n in nodes}
    edge_by_id = {e["id"]: e for e in edges}
    names = {n["name"].strip().lower() for n in nodes}
    added: dict[str, dict] = {}

    if len(mods) > MAX_MODIFICATIONS:
        issues.append(_issue("error", "mod_too_many", f"A scenario can have at most {MAX_MODIFICATIONS} modifications."))
    if len(nodes) + sum(m["type"] == "add_node" for m in mods) > MAX_NODES:
        issues.append(_issue("error", "mod_too_many_nodes", f"The modified graph would exceed {MAX_NODES} nodes."))

    for m in mods:
        if m["type"] != "add_node":
            continue
        if m["key"] in added:
            issues.append(_issue("error", "mod_duplicate_key", f"Two added nodes share the key '{m['key']}'."))
        lowered = m["name"].strip().lower()
        if lowered in names:
            issues.append(_issue("error", "mod_name_taken", f"A node named '{m['name']}' already exists."))
        names.add(lowered)
        added[m["key"]] = m

    def resolve(ref) -> str | None:
        if isinstance(ref, str):
            return added[ref]["name"] if ref in added else None
        return by_id[ref]["name"] if ref in by_id else None

    seen_edges = {(e["source_id"], e["destination_id"], e["relationship_type"]) for e in edges}
    touched: dict[tuple, int] = {}
    n_edges = len(edges) + sum(m["type"] == "add_edge" for m in mods)
    if n_edges > MAX_EDGES:
        issues.append(_issue("error", "mod_too_many_edges", f"The modified graph would exceed {MAX_EDGES} connections."))

    for i, m in enumerate(mods, start=1):
        t, where = m["type"], f"Modification {i}"
        if t == "set_capacity":
            node = by_id.get(m["node_id"])
            if node is None:
                issues.append(_issue("error", "mod_missing_node", f"{where}: the target node no longer exists."))
                continue
            if abs(node["capacity"] - m["capacity"]) < 1e-12:
                issues.append(_issue("warning", "mod_no_change", f"{where}: '{node['name']}' already has capacity {m['capacity']:g}.", [node["id"]]))
            if touched.get(("cap", node["id"])):
                issues.append(_issue("warning", "mod_overrides", f"{where}: capacity of '{node['name']}' is set more than once; the last value wins.", [node["id"]]))
            touched[("cap", node["id"])] = i
        elif t == "reduce_demand":
            node = by_id.get(m["node_id"])
            if node is None:
                issues.append(_issue("error", "mod_missing_node", f"{where}: the target node no longer exists."))
                continue
            if not _has_demand(node):
                issues.append(_issue("warning", "mod_no_demand", f"{where}: '{node['name']}' declares no demand, so reducing it changes nothing.", [node["id"]]))
        elif t == "add_edge":
            src, dst = resolve(m["source"]), resolve(m["destination"])
            if src is None or dst is None:
                issues.append(_issue("error", "mod_missing_node", f"{where}: the {'source' if src is None else 'destination'} of the new connection does not exist."))
                continue
            if m["source"] == m["destination"]:
                issues.append(_issue("error", "mod_self_loop", f"{where}: a node cannot depend on itself."))
                continue
            if isinstance(m["source"], int) and isinstance(m["destination"], int):
                key = (m["source"], m["destination"], m["relationship_type"])
                if key in seen_edges:
                    issues.append(_issue("error", "mod_duplicate_edge", f"{where}: that connection already exists."))
                seen_edges.add(key)
        elif t == "set_edge":
            edge = edge_by_id.get(m["edge_id"])
            if edge is None:
                issues.append(_issue("error", "mod_missing_edge", f"{where}: the connection no longer exists."))
                continue
            new_type = m.get("relationship_type", edge["relationship_type"])
            if new_type != edge["relationship_type"]:
                key = (edge["source_id"], edge["destination_id"], new_type)
                if key in seen_edges:
                    issues.append(_issue("error", "mod_duplicate_edge", f"{where}: a '{new_type}' connection between those nodes already exists."))
                seen_edges.add(key)
            if m.get("strength", edge["strength"]) == edge["strength"] and new_type == edge["relationship_type"]:
                issues.append(_issue("warning", "mod_no_change", f"{where}: the connection already has those values."))
    return issues


def apply_modifications(nodes: list[dict], edges: list[dict], mods: list[dict]) -> tuple[list[dict], list[dict]]:
    """Returns a modified COPY of the graph. Raises ModificationError if a modification is invalid."""
    errors = [i["message"] for i in check_modifications(nodes, edges, mods) if i["level"] == "error"]
    if errors:
        raise ModificationError(errors)
    out_nodes, out_edges = copy.deepcopy(nodes), copy.deepcopy(edges)
    by_id = {n["id"]: n for n in out_nodes}
    edge_by_id = {e["id"]: e for e in out_edges}
    next_node = max((n["id"] for n in out_nodes), default=0) + 1
    next_edge = max((e["id"] for e in out_edges), default=0) + 1
    xs = [n.get("pos_x", 0) for n in out_nodes] or [0]
    ys = [n.get("pos_y", 0) for n in out_nodes] or [0]
    keys: dict[str, int] = {}

    for m in mods:  # pass 1: new nodes
        if m["type"] != "add_node":
            continue
        slot = len(keys)
        node = {"id": next_node, "name": m["name"].strip(), "category": m["category"], "state": "operational",
                "capacity": float(m["capacity"]), "demand": 0.0, "importance": float(m["importance"]),
                "pos_x": min(xs) + slot * 240, "pos_y": max(ys) + 180, "added": True,
                "meta": {"synthetic": True, "unit": m.get("unit", ""), "demands": {}, "added_by_intervention": True}}
        out_nodes.append(node)
        by_id[next_node] = node
        keys[m["key"]] = next_node
        next_node += 1

    ref = lambda r: keys[r] if isinstance(r, str) else r  # noqa: E731
    for m in mods:  # pass 2: everything else, in order
        t = m["type"]
        if t == "set_capacity":
            by_id[m["node_id"]]["capacity"] = float(m["capacity"])
            by_id[m["node_id"]]["modified"] = True
        elif t == "reduce_demand":
            node, factor = by_id[m["node_id"]], 1 - m["reduce_pct"] / 100
            declared = (node.get("meta") or {}).get("demands")
            if isinstance(declared, dict):
                node["meta"]["demands"] = {k: v * factor if isinstance(v, (int, float)) and not isinstance(v, bool) else v
                                           for k, v in declared.items()}
            else:
                node["demand"] = node["demand"] * factor
            node["modified"] = True
        elif t == "add_edge":
            edge = {"id": next_edge, "source_id": ref(m["source"]), "destination_id": ref(m["destination"]),
                    "relationship_type": m["relationship_type"], "strength": float(m["strength"]),
                    "capacity": None, "added": True}
            out_edges.append(edge)
            edge_by_id[next_edge] = edge
            next_edge += 1
        elif t == "set_edge":
            edge = edge_by_id[m["edge_id"]]
            if "strength" in m:
                edge["strength"] = float(m["strength"])
            if "relationship_type" in m:
                edge["relationship_type"] = m["relationship_type"]
            edge["modified"] = True
    return out_nodes, out_edges


def describe_modifications(mods: list[dict], nodes: list[dict], edges: list[dict]) -> list[str]:
    """One readable sentence per modification (labels use the ORIGINAL graph)."""
    by_id = {n["id"]: n for n in nodes}
    edge_by_id = {e["id"]: e for e in edges}
    added = {m["key"]: m["name"] for m in mods if m["type"] == "add_node"}

    def name(ref) -> str:
        if isinstance(ref, str):
            return added.get(ref, str(ref))
        return by_id[ref]["name"] if ref in by_id else f"node #{ref}"

    out = []
    for m in mods:
        t = m["type"]
        if t == "set_capacity":
            node = by_id.get(m["node_id"])
            unit = f" {(node.get('meta') or {}).get('unit', '')}".rstrip() if node else ""
            was = f" (was {node['capacity']:g})" if node else ""
            out.append(f"Set capacity of '{name(m['node_id'])}' to {m['capacity']:g}{unit}{was}")
        elif t == "reduce_demand":
            out.append(f"Reduce demand of '{name(m['node_id'])}' by {m['reduce_pct']:g}%")
        elif t == "add_node":
            unit = f" {m.get('unit', '')}".rstrip()
            out.append(f"Add {m['category']} node '{m['name']}' (capacity {m['capacity']:g}{unit}, importance {m['importance']:g})")
        elif t == "add_edge":
            out.append(f"Add {m['relationship_type']} connection '{name(m['source'])}' -> '{name(m['destination'])}' (strength {m['strength']:g})")
        elif t == "set_edge":
            e = edge_by_id.get(m["edge_id"])
            if e is None:
                out.append(f"Change connection #{m['edge_id']}")
                continue
            parts = []
            if "strength" in m:
                parts.append(f"strength {e['strength']:g} -> {m['strength']:g}")
            if "relationship_type" in m:
                parts.append(f"type {e['relationship_type']} -> {m['relationship_type']}")
            out.append(f"Change connection '{name(e['source_id'])}' -> '{name(e['destination_id'])}': {', '.join(parts)}")
    return out


def fingerprint(nodes: list[dict], edges: list[dict]) -> str:
    """Stable hash of what the simulation depends on (ignores positions and display flags)."""
    payload = {
        "n": [[n["id"], n["name"], n["category"], n["state"], n["capacity"], n["demand"], n["importance"],
               (n.get("meta") or {}).get("demands"), (n.get("meta") or {}).get("unit")]
              for n in sorted(nodes, key=lambda n: n["id"])],
        "e": [[e["id"], e["source_id"], e["destination_id"], e["relationship_type"], e["strength"], e.get("capacity")]
              for e in sorted(edges, key=lambda e: e["id"])],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def graph_diff(a_nodes, a_edges, b_nodes, b_edges, limit: int = 8) -> list[str]:
    """Human-readable differences between two ORIGINAL (unmodified) graphs, a -> b."""
    out: list[str] = []
    an, bn = {n["id"]: n for n in a_nodes}, {n["id"]: n for n in b_nodes}
    for nid in sorted(set(an) | set(bn)):
        if nid not in bn:
            out.append(f"node '{an[nid]['name']}' was removed")
        elif nid not in an:
            out.append(f"node '{bn[nid]['name']}' was added")
        else:
            for f in ("capacity", "demand", "state", "importance"):
                if an[nid][f] != bn[nid][f]:
                    out.append(f"'{bn[nid]['name']}' {f}: {an[nid][f]:g} -> {bn[nid][f]:g}" if f != "state"
                               else f"'{bn[nid]['name']}' state: {an[nid][f]} -> {bn[nid][f]}")
            da, db = (an[nid].get("meta") or {}).get("demands"), (bn[nid].get("meta") or {}).get("demands")
            if da != db:
                out.append(f"'{bn[nid]['name']}' declared demands changed")
    ae, be = {e["id"]: e for e in a_edges}, {e["id"]: e for e in b_edges}
    for eid in sorted(set(ae) | set(be)):
        if eid not in be:
            out.append(f"connection #{eid} was removed")
        elif eid not in ae:
            out.append(f"connection #{eid} was added")
        elif (ae[eid]["strength"], ae[eid]["relationship_type"]) != (be[eid]["strength"], be[eid]["relationship_type"]):
            out.append(f"connection #{eid} changed: {ae[eid]['relationship_type']} {ae[eid]['strength']:g} -> "
                       f"{be[eid]['relationship_type']} {be[eid]['strength']:g}")
    if len(out) > limit:
        out = out[:limit] + [f"... and {len(out) - limit} more"]
    return out