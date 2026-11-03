"""Dependency propagation. Pure Python (networkx is used only to order the sweeps)."""
from dataclasses import dataclass

import networkx as nx

from .rules import EPS, MAX_ITERATIONS, MAX_WORK, RESOURCE_CATEGORIES


class SimulationLimitError(RuntimeError):
    """Raised when a simulation exceeds its work budget."""


@dataclass(frozen=True, slots=True)
class Val:
    a: float    # availability: fraction of baseline output the node can deliver
    out: float  # deliverable quantity (capacity x a), in the node's own unit
    lvl: float  # service level toward dependents


class Network:
    def __init__(self, nodes: list[dict], edges: list[dict], max_work: int = MAX_WORK):
        self.nodes = {n["id"]: n for n in nodes}
        self.edges = sorted(
            (e for e in edges if e["source_id"] in self.nodes and e["destination_id"] in self.nodes),
            key=lambda e: e["id"])
        self.incoming: dict[int, list[dict]] = {nid: [] for nid in self.nodes}
        for e in self.edges:
            self.incoming[e["destination_id"]].append(e)
        self.cap = {nid: float(n["capacity"]) for nid, n in self.nodes.items()}
        self.flow = {e["id"] for e in self.edges if self._same_resource(e)}
        self.notes: list[dict] = []
        self.demand = self._build_demand()
        self.quantity = {nid for nid, n in self.nodes.items()
                         if n["category"] in RESOURCE_CATEGORIES and self.cap[nid] > 0 and self.demand[nid] > 0}
        self.order = self._sweep_order()
        self.max_work = max_work
        self.work = 0

    # ---------- construction ----------
    def _same_resource(self, e: dict) -> bool:
        a = self.nodes[e["source_id"]]["category"]
        return a == self.nodes[e["destination_id"]]["category"] and a in RESOURCE_CATEGORIES

    def _note(self, code: str, message: str) -> None:
        self.notes.append({"code": code, "message": message})

    def _needs(self, nid: int) -> dict[str, float]:
        """What a node requests from its suppliers, per resource."""
        node = self.nodes[nid]
        declared = (node.get("meta") or {}).get("demands")
        if isinstance(declared, dict):
            needs: dict[str, float] = {}
            for res, amount in declared.items():
                if isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount < 0:
                    self._note("bad_demand", f"'{node['name']}': the demand for '{res}' is not a "
                                             "non-negative number and was ignored.")
                elif amount > 0:
                    needs[res] = float(amount)
            return needs
        if node["demand"] > 0:
            kinds = {self.nodes[e["source_id"]]["category"] for e in self.incoming[nid]} & RESOURCE_CATEGORIES
            if len(kinds) == 1:
                return {next(iter(kinds)): float(node["demand"])}
            self._note("ambiguous_demand",
                       f"'{node['name']}' has demand {node['demand']:g} but "
                       f"{'no resource supplier' if not kinds else 'several resource suppliers'}; "
                       "it was ignored. Add meta.demands, e.g. {\"electricity\": 50}, to say what it consumes.")
        return {}

    def _build_demand(self) -> dict[int, float]:
        total = {nid: 0.0 for nid in self.nodes}
        seen: set[tuple[int, int]] = set()
        for nid in sorted(self.nodes):
            needs = self._needs(nid)
            for e in self.incoming[nid]:
                s = self.nodes[e["source_id"]]
                if s["category"] in RESOURCE_CATEGORIES and e["id"] not in self.flow \
                        and (s["id"], nid) not in seen:
                    seen.add((s["id"], nid))
                    total[s["id"]] += needs.get(s["category"], 0.0)
        return total

    def _sweep_order(self) -> list[int]:
        """Suppliers before dependents; members of a cycle sit together, sorted by id."""
        g = nx.DiGraph()
        g.add_nodes_from(self.nodes)
        g.add_edges_from((e["source_id"], e["destination_id"]) for e in self.edges)
        cond = nx.condensation(g)
        order: list[int] = []
        for c in nx.lexicographical_topological_sort(cond, key=lambda c: min(cond.nodes[c]["members"])):
            order.extend(sorted(cond.nodes[c]["members"]))
        return order

    # ---------- evaluation ----------
    def evaluate(self, nid: int, own: float, vals: dict[int, Val]) -> Val:
        flow_in, has_flow = 0.0, False
        required: list[float] = []
        backup, has_backup, partial = 0.0, False, 1.0
        for e in self.incoming[nid]:
            s, k = vals[e["source_id"]], e["strength"]
            if e["id"] in self.flow:
                has_flow = True
                flow_in += s.out * k
            elif e["relationship_type"] == "backup":
                has_backup = True
                backup += k * s.lvl
            elif e["relationship_type"] == "required":
                required.append(1.0 - k * (1.0 - s.lvl))
            else:  # partial
                partial *= 1.0 - k * (1.0 - s.lvl)
        cap = self.cap[nid]
        flow_level = min(1.0, flow_in / cap) if has_flow and cap > 0 else 1.0
        if required:
            level = min(required)
            if has_backup:
                level = min(1.0, level + backup)
        elif has_backup:
            level = min(1.0, backup)
        else:
            level = 1.0
        a = max(0.0, min(own, flow_level, level)) * partial
        out = cap * a
        lvl = min(1.0, out / self.demand[nid]) if nid in self.quantity else a
        return Val(a, out, lvl)

    def _initial(self, own: dict[int, float]) -> dict[int, Val]:
        vals = {}
        for nid in self.nodes:
            out = self.cap[nid] * own[nid]
            lvl = min(1.0, out / self.demand[nid]) if nid in self.quantity else own[nid]
            vals[nid] = Val(own[nid], out, lvl)
        return vals

    def solve(self, own: dict[int, float], max_iterations: int = MAX_ITERATIONS):
        """Start from the best case and sweep until nothing changes. Returns (values, sweeps, converged)."""
        vals = self._initial(own)
        cost = len(self.nodes) + len(self.edges)
        for sweep in range(1, max_iterations + 1):
            self.work += cost
            if self.work > self.max_work:
                raise SimulationLimitError(
                    "The simulation is too large for the configured work limit. Reduce the graph or the number of events.")
            delta = 0.0
            for nid in self.order:
                new, old = self.evaluate(nid, own[nid], vals), vals[nid]
                delta = max(delta, abs(new.a - old.a), abs(new.lvl - old.lvl))
                vals[nid] = new
            if delta < EPS:
                return vals, sweep, True
        return vals, max_iterations, False