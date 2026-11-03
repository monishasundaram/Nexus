import copy

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import MODEL_VERSION
from ..database import get_db
from ..engine.propagation import SimulationLimitError
from ..engine.simulate import SimulationInputError, run_simulation
from ..models import Edge, Environment, Node, ScenarioEvent, Simulation, SimulationResult, utcnow
from .common import commit
from .scenarios import get_scenario_or_404

router = APIRouter()

RESULT_KEYS = ("capacity", "unserved", "timeline", "events", "solver", "evaluated_at", "formula", "limitations")


def _snapshot(db: Session, scenario) -> dict:
    """A frozen copy of everything the engine needs, so the run can always be reproduced."""
    env = db.get(Environment, scenario.environment_id)
    nodes = db.scalars(select(Node).where(Node.environment_id == env.id).order_by(Node.id)).all()
    edges = db.scalars(select(Edge).where(Edge.environment_id == env.id).order_by(Edge.id)).all()
    events = db.scalars(select(ScenarioEvent).where(ScenarioEvent.scenario_id == scenario.id)
                        .order_by(ScenarioEvent.start_time, ScenarioEvent.id)).all()
    return {
        "environment": {"id": env.id, "name": env.name, "model_version": env.model_version},
        "scenario": {"id": scenario.id, "name": scenario.name, "version": scenario.version,
                     "description": scenario.description, "assumptions": list(scenario.assumptions or [])},
        "nodes": [{"id": n.id, "name": n.name, "category": n.category, "state": n.state,
                   "capacity": n.capacity, "demand": n.demand, "importance": n.importance,
                   "meta": copy.deepcopy(n.meta or {})} for n in nodes],
        "edges": [{"id": e.id, "source_id": e.source_id, "destination_id": e.destination_id,
                   "relationship_type": e.relationship_type, "strength": e.strength,
                   "capacity": e.capacity} for e in edges],
        "events": [{"id": e.id, "event_type": e.event_type, "target_node_id": e.target_node_id,
                    "params": dict(e.params or {}), "start_time": e.start_time, "duration": e.duration}
                   for e in events],
    }


def _head(sim: Simulation) -> dict:
    snap = sim.baseline_snapshot or {}
    env, scn = snap.get("environment", {}), snap.get("scenario", {})
    return {
        "id": sim.id, "scenario_id": sim.scenario_id, "scenario_name": scn.get("name", ""),
        "scenario_version": sim.scenario_version, "environment_id": env.get("id"),
        "environment_name": env.get("name", ""), "model_version": sim.model_version, "status": sim.status,
        "started_at": sim.started_at.isoformat(),
        "completed_at": sim.completed_at.isoformat() if sim.completed_at else None,
        "error_summary": sim.error_summary,
        "node_count": len(snap.get("nodes", [])), "edge_count": len(snap.get("edges", [])),
    }


def _result_of(db: Session, sim_id: int):
    return db.scalar(select(SimulationResult).where(SimulationResult.simulation_id == sim_id))


def _present(db: Session, sim: Simulation) -> dict:
    out = _head(sim)
    res = _result_of(db, sim.id)
    out["result"] = None
    if res is not None:
        agg = res.aggregate_metrics
        out["result"] = {"metrics": agg["metrics"], "node_results": res.node_results,
                         "traces": res.dependency_traces, "warnings": res.warnings,
                         "assumptions": res.assumptions, **{k: agg[k] for k in RESULT_KEYS}}
    return out


def get_simulation_or_404(db: Session, sim_id: int) -> Simulation:
    sim = db.get(Simulation, sim_id)
    if sim is None:
        raise HTTPException(404, "Simulation not found")
    return sim


def _record_failure(db: Session, scenario, snap: dict, message: str) -> None:
    db.add(Simulation(scenario_id=scenario.id, scenario_version=scenario.version, baseline_snapshot=snap,
                      model_version=MODEL_VERSION, status="failed", completed_at=utcnow(),
                      error_summary=message[:500]))
    commit(db)


@router.post("/scenarios/{sid}/simulate", status_code=201)
def run_scenario(sid: int, db: Session = Depends(get_db)):
    scenario = get_scenario_or_404(db, sid)
    if scenario.status != "final":
        raise HTTPException(409, "Finalize this scenario version before running it, "
                                 "so the simulation stays tied to an exact version.")
    snap = _snapshot(db, scenario)
    started = utcnow()
    try:
        result = run_simulation(snap["nodes"], snap["edges"], snap["events"])
    except SimulationInputError as exc:
        raise HTTPException(422, f"The scenario cannot be simulated: {exc}")
    except SimulationLimitError as exc:
        _record_failure(db, scenario, snap, str(exc))
        raise HTTPException(422, str(exc))
    except Exception:
        _record_failure(db, scenario, snap, "Unexpected internal error while simulating.")
        raise HTTPException(500, "The simulation failed unexpectedly. Nothing was changed.")

    sim = Simulation(scenario_id=sid, scenario_version=scenario.version, baseline_snapshot=snap,
                     model_version=MODEL_VERSION, status="completed", started_at=started,
                     completed_at=utcnow())
    db.add(sim)
    db.flush()
    db.add(SimulationResult(
        simulation_id=sim.id,
        node_results=result["node_results"],
        aggregate_metrics={"metrics": result["metrics"], **{k: result[k] for k in RESULT_KEYS}},
        dependency_traces=result["traces"],
        warnings=result["warnings"],
        assumptions=result["assumptions"] + [f"Scenario: {a}" for a in snap["scenario"]["assumptions"]],
    ))
    commit(db)
    db.refresh(sim)
    return _present(db, sim)


@router.get("/simulations")
def list_simulations(scenario_id: int | None = None, limit: int = Query(50, ge=1, le=200),
                     db: Session = Depends(get_db)):
    q = select(Simulation).order_by(Simulation.started_at.desc(), Simulation.id.desc()).limit(limit)
    if scenario_id is not None:
        q = q.where(Simulation.scenario_id == scenario_id)
    sims = db.scalars(q).all()
    results = {}
    if sims:
        results = {r.simulation_id: r for r in db.scalars(
            select(SimulationResult).where(SimulationResult.simulation_id.in_([s.id for s in sims])))}
    out = []
    for s in sims:
        row, res = _head(s), results.get(s.id)
        row["metrics"] = ({k: res.aggregate_metrics["metrics"][k] for k in
                           ("impact_score", "affected_nodes", "failed_nodes", "degraded_nodes")}
                          if res else None)
        out.append(row)
    return out


@router.get("/simulations/{sim_id}")
def get_simulation(sim_id: int, db: Session = Depends(get_db)):
    return _present(db, get_simulation_or_404(db, sim_id))


@router.get("/simulations/{sim_id}/snapshot")
def get_snapshot(sim_id: int, db: Session = Depends(get_db)):
    return get_simulation_or_404(db, sim_id).baseline_snapshot


@router.delete("/simulations/{sim_id}", status_code=204)
def delete_simulation(sim_id: int, db: Session = Depends(get_db)):
    db.delete(get_simulation_or_404(db, sim_id))  # the database cascades to the result
    commit(db)