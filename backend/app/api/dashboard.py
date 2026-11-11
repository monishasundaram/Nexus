from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Comparison, Environment, Node, Scenario, Simulation, SimulationResult
from .comparisons import comparison_summary

router = APIRouter()

RECENT = 5
TOP_NODES = 8
HISTORY = 200  # most affected nodes are counted over the latest completed simulations


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    recent = db.scalars(select(Simulation).order_by(Simulation.started_at.desc(), Simulation.id.desc())
                        .limit(RECENT)).all()
    results = {r.simulation_id: r for r in db.scalars(
        select(SimulationResult).where(SimulationResult.simulation_id.in_([s.id for s in recent])))} if recent else {}
    scenarios = {s.id: s for s in db.scalars(
        select(Scenario).where(Scenario.id.in_([s.scenario_id for s in recent])))} if recent else {}

    recent_rows = []
    for s in recent:
        res, scn = results.get(s.id), scenarios.get(s.scenario_id)
        metrics = res.aggregate_metrics.get("metrics", {}) if res else {}
        recent_rows.append({
            "id": s.id, "scenario_id": s.scenario_id,
            "scenario_name": scn.name if scn else "", "scenario_version": s.scenario_version,
            "status": s.status, "started_at": s.started_at.isoformat(),
            "impact_score": metrics.get("impact_score"), "affected_nodes": metrics.get("affected_nodes"),
        })

    done = db.scalars(select(Simulation.id).where(Simulation.status == "completed")
                      .order_by(Simulation.id.desc()).limit(HISTORY)).all()
    counts: Counter = Counter()
    categories: dict[str, str] = {}
    if done:
        for res in db.scalars(select(SimulationResult).where(SimulationResult.simulation_id.in_(done))):
            for n in res.node_results:
                if n.get("trend") == "worse":
                    counts[n["name"]] += 1
                    categories[n["name"]] = n.get("category", "")
    top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP_NODES]

    cats = db.execute(select(Node.category, func.count()).group_by(Node.category)).all()
    return {
        "environments": db.scalar(select(func.count(Environment.id))),
        "scenarios": db.scalar(select(func.count(Scenario.id))),
        "completed_simulations": db.scalar(
            select(func.count(Simulation.id)).where(Simulation.status == "completed")),
        "recent_simulations": recent_rows,
        "category_distribution": [{"category": c, "count": n} for c, n in cats],
        "most_affected_nodes": [{"name": n, "category": categories[n], "count": c} for n, c in top],
        "runs_counted": len(done),
        "recent_comparisons": [comparison_summary(db, c) for c in db.scalars(
            select(Comparison).order_by(Comparison.created_at.desc(), Comparison.id.desc()).limit(RECENT))],
    }