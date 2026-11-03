"""Plain-dict versions of the NEXUS Campus data, for running the engine without a database."""
import copy

from .campus import CAMPUS_EDGES, CAMPUS_NODES


def campus_graph():
    ids = {spec["name"]: i for i, spec in enumerate(CAMPUS_NODES, start=1)}
    nodes = [dict(id=ids[s["name"]], name=s["name"], category=s["category"], state="operational",
                  capacity=s["capacity"], demand=s["demand"], importance=s["importance"],
                  meta=copy.deepcopy(s["meta"])) for s in CAMPUS_NODES]
    edges = [dict(id=i, source_id=ids[a], destination_id=ids[b], relationship_type=rel,
                  strength=strength, capacity=None)
             for i, (a, b, rel, strength) in enumerate(CAMPUS_EDGES, start=1)]
    return ids, nodes, edges


def sample_events(spec: dict, ids: dict[str, int]) -> list[dict]:
    return [dict(id=i, event_type=e["event_type"], target_node_id=ids[e["target"]],
                 params=dict(e["params"]), start_time=e["start_time"], duration=e["duration"])
            for i, e in enumerate(spec["events"], start=1)]