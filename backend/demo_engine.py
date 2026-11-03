"""Runs the four NEXUS Campus sample scenarios through the real engine.
Usage (from the backend folder, venv active):  python demo_engine.py"""
from app.engine.simulate import run_simulation
from app.seed.plain import campus_graph, sample_events
from app.seed.scenarios import SAMPLE_SCENARIOS


def main() -> None:
    for spec in SAMPLE_SCENARIOS:
        ids, nodes, edges = campus_graph()
        r = run_simulation(nodes, edges, sample_events(spec, ids))
        m = r["metrics"]
        print(f"\n=== {spec['name']} ===")
        print(f"affected {m['affected_nodes']} of {m['total_nodes']} nodes "
              f"({m['direct_nodes']} direct, {m['indirect_nodes']} indirect) | "
              f"failed {m['failed_nodes']} | degraded {m['degraded_nodes']} | impact score {m['impact_score']:.3f}")
        for key, v in r["unserved"].items():
            print(f"unserved {key}: {v['baseline']:g} -> {v['scenario']:g}")
        worst = sorted((n for n in r["node_results"] if n["trend"] == "worse"), key=lambda n: n["delta"])[:6]
        for n in worst:
            print(f"  {n['name']:<28} {n['baseline_level']:>5.0%} -> {n['level']:>5.0%}  ({n['impact']})")


if __name__ == "__main__":
    main()