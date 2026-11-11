from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..engine.compare import ComparisonError, compare
from ..models import Comparison, Scenario, Simulation, SimulationResult, utcnow
from ..schemas import ComparisonIn
from .common import commit

router = APIRouter()

RECENT_LIMIT = 20


def load_payloads(db: Session, ids: list[int]) -> list[dict]:
    """Stored simulations in the requested order, shaped for the comparison engine."""
    sims = {s.id: s for s in db.scalars(select(Simulation).where(Simulation.id.in_(ids)))}
    results = {r.simulation_id: r for r in db.scalars(
        select(SimulationResult).where(SimulationResult.simulation_id.in_(ids)))}
    out = []
    for sid in ids:
        sim, res = sims.get(sid), results.get(sid)
        if sim is None:
            raise HTTPException(404, f"Simulation {sid} does not exist (it may have been deleted).")
        if sim.status != "completed" or res is None:
            raise HTTPException(422, f"Simulation {sid} has no completed result to compare.")
        snap = sim.baseline_snapshot
        agg = res.aggregate_metrics
        out.append({
            "id": sim.id, "scenario_id": sim.scenario_id, "scenario_name": snap["scenario"]["name"],
            "scenario_version": sim.scenario_version, "environment_id": snap["environment"]["id"],
            "environment_name": snap["environment"]["name"], "model_version": sim.model_version,
            "started_at": sim.started_at.isoformat(), "snapshot": snap,
            "result": {"metrics": agg["metrics"], "node_results": res.node_results, "traces": res.dependency_traces,
                       "warnings": res.warnings, "capacity": agg["capacity"], "unserved": agg["unserved"],
                       "timeline": agg["timeline"], "events": agg["events"], "solver": agg["solver"],
                       "evaluated_at": agg["evaluated_at"]},
        })
    return out


def _run(db: Session, ids: list[int]) -> dict:
    try:
        return compare(load_payloads(db, ids))
    except ComparisonError as exc:
        raise HTTPException(422, str(exc))


@router.post("/comparisons", status_code=201)
def create_comparison(body: ComparisonIn, db: Session = Depends(get_db)):
    result = _run(db, body.simulation_ids)  # refuses incompatible selections before anything is stored
    existing = next((c for c in db.scalars(select(Comparison).order_by(Comparison.id.desc()))
                     if c.simulation_ids == body.simulation_ids), None)
    if existing is None:
        existing = Comparison(simulation_ids=list(body.simulation_ids))
        db.add(existing)
    else:
        existing.created_at = utcnow()
    commit(db)
    db.refresh(existing)
    return {"id": existing.id, "created_at": existing.created_at.isoformat(), **result}


@router.get("/comparisons")
def list_comparisons(db: Session = Depends(get_db)):
    rows = db.scalars(select(Comparison).order_by(Comparison.created_at.desc(), Comparison.id.desc())
                      .limit(RECENT_LIMIT)).all()
    return [comparison_summary(db, c) for c in rows]


def comparison_summary(db: Session, c: Comparison) -> dict:
    sims = {s.id: s for s in db.scalars(select(Simulation).where(Simulation.id.in_(c.simulation_ids)))}
    labels = []
    for sid in c.simulation_ids:
        s = sims.get(sid)
        name = (s.baseline_snapshot or {}).get("scenario", {}).get("name", "") if s else ""
        labels.append(f"{name} v{s.scenario_version} (#{sid})" if s else f"deleted simulation #{sid}")
    return {"id": c.id, "created_at": c.created_at.isoformat(), "simulation_ids": c.simulation_ids,
            "labels": labels, "available": all(sid in sims for sid in c.simulation_ids)}


@router.get("/comparisons/{cid}")
def get_comparison(cid: int, db: Session = Depends(get_db)):
    c = db.get(Comparison, cid)
    if c is None:
        raise HTTPException(404, "Comparison not found")
    return {"id": c.id, "created_at": c.created_at.isoformat(), **_run(db, c.simulation_ids)}


@router.delete("/comparisons/{cid}", status_code=204)
def delete_comparison(cid: int, db: Session = Depends(get_db)):
    c = db.get(Comparison, cid)
    if c is None:
        raise HTTPException(404, "Comparison not found")
    db.delete(c)
    commit(db)