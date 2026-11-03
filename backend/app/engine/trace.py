"""Classification of affected nodes and dependency traces. Pure Python."""
from .events import EVENT_TYPES
from .rules import EPS, rnd


def event_label(e: dict, names: dict[int, str]) -> str:
    spec = EVENT_TYPES[e["event_type"]]
    extra = f" {e['params'][spec['param']]:g}%" if spec["param"] else ""
    return f"{spec['label']}{extra} on '{names.get(e['target_node_id'], '?')}' (t={e['start_time']:g}h)"


def state_label(level: float, maintenance: bool = False) -> str:
    if level >= 1 - EPS:
        return "operational"
    if level <= EPS:
        return "maintenance" if maintenance else "failed"
    return "degraded"


def _parents(net, base, vals, own_now, indirect: list[int]) -> dict[int, dict]:
    """For each indirectly affected node, the incoming edge whose supplier explains the loss best.

    Counterfactual test: reset one supplier to its baseline and see how much of the node's level comes back.
    """
    parents: dict[int, dict] = {}
    for nid in indirect:
        best = None
        for e in net.incoming[nid]:
            s = e["source_id"]
            drop = (base[s].out - vals[s].out) if e["id"] in net.flow else (base[s].lvl - vals[s].lvl)
            if drop <= EPS:
                continue
            kept = vals[s]
            vals[s] = base[s]
            try:
                recovery = net.evaluate(nid, own_now[nid][0], vals).lvl - vals[nid].lvl
            finally:
                vals[s] = kept
            key = (round(max(recovery, 0.0), 9), round(drop, 9), -e["id"])
            if best is None or key > best[0]:
                best = (key, e)
        if best is not None:
            parents[nid] = best[1]
    return parents


def _chain(nid: int, parents: dict[int, dict]) -> tuple[list[int], list[int]]:
    nodes, edges, seen, cur = [nid], [], {nid}, nid
    while cur in parents:
        e = parents[cur]
        cur = e["source_id"]
        if cur in seen:
            break
        seen.add(cur)
        nodes.append(cur)
        edges.append(e["id"])
    return nodes[::-1], edges[::-1]


def analyse(net, base, vals, own_now, own_base, events_by_id):
    """Per-node results and dependency traces for one snapshot."""
    ids = sorted(net.nodes)
    names = {nid: net.nodes[nid]["name"] for nid in ids}
    loss = {nid: base[nid].lvl - vals[nid].lvl for nid in ids}
    affected = {nid for nid in ids if loss[nid] > EPS}
    direct = {nid for nid in affected if own_now[nid][0] < own_base[nid] - EPS}
    indirect = sorted(affected - direct)
    parents = _parents(net, base, vals, own_now, indirect)

    node_results = []
    for nid in ids:
        n = net.nodes[nid]
        active = [events_by_id[i] for i in own_now[nid][1]]
        maintenance = any(e["event_type"] == "maintenance" for e in active)
        node_results.append({
            "node_id": nid, "name": names[nid], "category": n["category"], "importance": n["importance"],
            "baseline_level": rnd(base[nid].lvl), "level": rnd(vals[nid].lvl),
            "delta": rnd(vals[nid].lvl - base[nid].lvl),
            "baseline_state": state_label(base[nid].lvl, n["state"] == "maintenance"),
            "state": state_label(vals[nid].lvl, maintenance),
            "impact": "direct" if nid in direct else "indirect" if nid in affected else "none",
            "trend": "worse" if loss[nid] > EPS else "better" if -loss[nid] > EPS else "same",
            "absorbed": nid not in affected and own_now[nid][0] < own_base[nid] - EPS,
            "event_ids": list(own_now[nid][1]),
            "availability": rnd(vals[nid].a), "output": rnd(vals[nid].out), "capacity": net.cap[nid],
        })

    traces = []
    for nid in ids:
        if nid not in affected:
            continue
        chain, edge_ids = _chain(nid, parents)
        origin = chain[0]
        event_ids = list(own_now[origin][1]) if origin in direct else []
        labels = [event_label(events_by_id[i], names) for i in event_ids]
        b, lv = base[nid].lvl, vals[nid].lvl
        if nid in direct:
            text = f"{names[nid]} is directly affected by {'; '.join(labels)}. Its service level fell from {b:.0%} to {lv:.0%}."
        elif nid in parents:
            e = parents[nid]
            s, flow = e["source_id"], e["id"] in net.flow
            sb, sl = (base[s].a, vals[s].a) if flow else (base[s].lvl, vals[s].lvl)
            kind = "flow" if flow else e["relationship_type"]
            text = (f"{names[nid]} is indirectly affected through its {kind} dependency on {names[s]} "
                    f"(supplier level {sb:.0%} -> {sl:.0%}). Its service level fell from {b:.0%} to {lv:.0%}.")
            if len(chain) > 2:
                text += f" Chain: {' -> '.join(names[i] for i in chain)}."
            if labels:
                text += f" Origin: {labels[0]}{' (and more)' if len(labels) > 1 else ''}."
        else:
            text = f"{names[nid]} lost service ({b:.0%} -> {lv:.0%}) but no single supplier explains the loss."
        traces.append({
            "node_id": nid, "node_name": names[nid],
            "impact": "direct" if nid in direct else "indirect",
            "baseline_level": rnd(b), "level": rnd(lv),
            "event_ids": event_ids, "path": chain, "path_names": [names[i] for i in chain],
            "edge_ids": edge_ids, "explanation": text,
        })
    return node_results, traces