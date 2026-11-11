import copy
from collections import defaultdict
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..engine.events import EVENT_TYPES
from ..engine.modifications import check_modifications, describe_modifications
from ..engine.scenario_validation import validate_scenario
from ..models import Edge, Environment, Node, Scenario, ScenarioEvent, Simulation
from ..schemas import (EventIn, EventOut, ModificationsIn, ScenarioIn, ScenarioOut,
                       ScenarioValidationReport)
from ..seed.scenarios import SAMPLE_SCENARIOS
from .common import commit, get_env_or_404, touch

router = APIRouter()


# ---------- helpers ----------
def get_scenario_or_404(db: Session, sid: int) -> Scenario:
    s = db.get(Scenario, sid)
    if s is None:
        raise HTTPException(404, "Scenario not found")
    return s


def _events_of(db: Session, sid: int) -> list[ScenarioEvent]:
    return list(db.scalars(select(ScenarioEvent).where(ScenarioEvent.scenario_id == sid)
                           .order_by(ScenarioEvent.start_time, ScenarioEvent.id)))


def _present(db: Session, scenarios: list[Scenario]) -> list[ScenarioOut]:
    ids = [s.id for s in scenarios]
    events: dict[int, list[EventOut]] = defaultdict(list)
    sims: dict[int, int] = {}
    names: dict[int, str] = {}
    if ids:
        for ev in db.scalars(select(ScenarioEvent).where(ScenarioEvent.scenario_id.in_(ids))
                             .order_by(ScenarioEvent.start_time, ScenarioEvent.id)):
            events[ev.scenario_id].append(EventOut.model_validate(ev))
        sims = {r[0]: r[1] for r in db.execute(
            select(Simulation.scenario_id, func.count()).where(Simulation.scenario_id.in_(ids))
            .group_by(Simulation.scenario_id))}
        env_ids = list({s.environment_id for s in scenarios})
        names = {e.id: e.name for e in db.scalars(select(Environment).where(Environment.id.in_(env_ids)))}
        out = []
    graphs: dict[int, tuple[list[dict], list[dict]]] = {}
    for s in scenarios:
        o = ScenarioOut.model_validate(s)
        o.events = events.get(s.id, [])
        o.simulation_count = sims.get(s.id, 0)
        o.environment_name = names.get(s.environment_id, "")
        if s.modifications:
            if s.environment_id not in graphs:
                graphs[s.environment_id] = _graph_dicts(db, s.environment_id)
            o.modification_labels = describe_modifications(s.modifications, *graphs[s.environment_id])
        out.append(o)
    return out


def _graph_dicts(db: Session, env_id: int) -> tuple[list[dict], list[dict]]:
    nodes = db.scalars(select(Node).where(Node.environment_id == env_id).order_by(Node.id)).all()
    edges = db.scalars(select(Edge).where(Edge.environment_id == env_id).order_by(Edge.id)).all()
    return (
        [{"id": n.id, "name": n.name, "category": n.category, "state": n.state, "capacity": n.capacity,
          "demand": n.demand, "importance": n.importance, "meta": n.meta or {}} for n in nodes],
        [{"id": e.id, "source_id": e.source_id, "destination_id": e.destination_id,
          "relationship_type": e.relationship_type, "strength": e.strength, "capacity": e.capacity} for e in edges])


def _ensure_name_free(db: Session, env_id: int, name: str, exclude_id: int | None = None):
    q = select(Scenario.id).where(Scenario.environment_id == env_id,
                                  func.lower(Scenario.name) == name.lower())
    if exclude_id is not None:
        q = q.where(Scenario.id != exclude_id)
    if db.scalar(q) is not None:
        raise HTTPException(409, f"A scenario named '{name}' already exists in this environment. "
                                 "Use New version on it, or choose another name.")


def _check_targets(db: Session, env_id: int, events: list[EventIn]):
    node_ids = set(db.scalars(select(Node.id).where(Node.environment_id == env_id)))
    for ev in events:
        if ev.target_node_id not in node_ids:
            raise HTTPException(422, f"Target node {ev.target_node_id} does not exist in this environment.")


def _add_events(db: Session, scenario_id: int, events: list[EventIn]):
    for ev in events:
        db.add(ScenarioEvent(scenario_id=scenario_id, event_type=ev.event_type,
                             target_node_id=ev.target_node_id, params=dict(ev.params),
                             start_time=ev.start_time, duration=ev.duration))


def _clone_events(db: Session, src_id: int, dst_id: int):
    for ev in _events_of(db, src_id):
        db.add(ScenarioEvent(scenario_id=dst_id, event_type=ev.event_type,
                             target_node_id=ev.target_node_id, params=copy.deepcopy(ev.params),
                             start_time=ev.start_time, duration=ev.duration))


def _validate(db: Session, s: Scenario) -> dict:
    nodes = db.scalars(select(Node).where(Node.environment_id == s.environment_id)).all()
    report = validate_scenario(
        [{"id": n.id, "name": n.name, "category": n.category, "state": n.state,
          "capacity": n.capacity} for n in nodes],
        [{"id": e.id, "event_type": e.event_type, "target_node_id": e.target_node_id,
          "params": e.params or {}, "start_time": e.start_time, "duration": e.duration}
         for e in _events_of(db, s.id)])
    if s.modifications:
        issues = check_modifications(*_graph_dicts(db, s.environment_id), s.modifications)
        rank = {"error": 0, "warning": 1, "info": 2}
        report["issues"] = sorted(report["issues"] + issues, key=lambda i: rank[i["level"]])
        report["error_count"] = sum(i["level"] == "error" for i in report["issues"])
        report["warning_count"] = sum(i["level"] == "warning" for i in report["issues"])
        report["valid"] = report["error_count"] == 0
        report["stats"]["modification_count"] = len(s.modifications)
    return report


def _free_copy_name(db: Session, env_id: int, base: str) -> str:
    taken = {n.lower() for n in db.scalars(select(Scenario.name).where(Scenario.environment_id == env_id))}
    base = base[:100]
    candidate, i = f"{base} (copy)", 2
    while candidate.lower() in taken:
        candidate = f"{base} (copy {i})"
        i += 1
    return candidate


# ---------- reference data ----------
@router.get("/event-types")
def list_event_types():
    return [{"type": k, **v} for k, v in EVENT_TYPES.items()]


# ---------- library ----------
@router.get("/scenarios", response_model=list[ScenarioOut])
def list_scenarios(
    environment_id: int | None = None,
    event_type: str | None = None,
    q: str | None = Query(None, max_length=120),
    archived: bool = False,
    sort: Literal["updated", "name"] = "updated",
    db: Session = Depends(get_db),
):
    query = select(Scenario).where(Scenario.is_archived.is_(archived))
    if environment_id is not None:
        query = query.where(Scenario.environment_id == environment_id)
    if event_type:
        query = query.where(Scenario.id.in_(
            select(ScenarioEvent.scenario_id).where(ScenarioEvent.event_type == event_type)))
    if q and q.strip():
        query = query.where(func.lower(Scenario.name).contains(q.strip().lower(), autoescape=True))
    order = Scenario.updated_at.desc() if sort == "updated" else func.lower(Scenario.name)
    return _present(db, list(db.scalars(query.order_by(order, Scenario.version.desc()))))


@router.get("/scenarios/{sid}", response_model=ScenarioOut)
def get_scenario(sid: int, db: Session = Depends(get_db)):
    return _present(db, [get_scenario_or_404(db, sid)])[0]


# ---------- create / edit ----------
@router.post("/environments/{env_id}/scenarios", response_model=ScenarioOut, status_code=201)
def create_scenario(env_id: int, body: ScenarioIn, db: Session = Depends(get_db)):
    get_env_or_404(db, env_id)
    _ensure_name_free(db, env_id, body.name)
    _check_targets(db, env_id, body.events)
    s = Scenario(environment_id=env_id, name=body.name, description=body.description,
                 assumptions=list(body.assumptions), status="draft", version=1)
    db.add(s)
    db.flush()
    _add_events(db, s.id, body.events)
    commit(db)
    db.refresh(s)
    return _present(db, [s])[0]


@router.put("/scenarios/{sid}", response_model=ScenarioOut)
def update_scenario(sid: int, body: ScenarioIn, db: Session = Depends(get_db)):
    s = get_scenario_or_404(db, sid)
    if s.status != "draft":
        raise HTTPException(409, "This version is final and cannot be edited. Create a new version instead.")
    if body.name != s.name:
        siblings = db.scalar(select(func.count(Scenario.id)).where(
            Scenario.environment_id == s.environment_id, Scenario.name == s.name, Scenario.id != s.id)) or 0
        if siblings:
            raise HTTPException(409, "Other versions share this name, so it cannot be changed. "
                                     "Duplicate the scenario to start a new lineage.")
        _ensure_name_free(db, s.environment_id, body.name, exclude_id=s.id)
    _check_targets(db, s.environment_id, body.events)
    db.execute(delete(ScenarioEvent).where(ScenarioEvent.scenario_id == s.id))
    _add_events(db, s.id, body.events)
    s.name, s.description, s.assumptions = body.name, body.description, list(body.assumptions)
    touch(s)
    commit(db)
    db.refresh(s)
    return _present(db, [s])[0]


# ---------- validation and lifecycle ----------

@router.put("/scenarios/{sid}/modifications", response_model=ScenarioOut)
def set_modifications(sid: int, body: ModificationsIn, db: Session = Depends(get_db)):
    s = get_scenario_or_404(db, sid)
    if s.status != "draft":
        raise HTTPException(409, "This version is final and cannot be edited. Create a new version instead.")
    mods = [m.model_dump(exclude_none=True) for m in body.modifications]
    errors = [i["message"] for i in check_modifications(*_graph_dicts(db, s.environment_id), mods)
              if i["level"] == "error"]
    if errors:
        raise HTTPException(422, errors[0])
    s.modifications = mods
    touch(s)
    commit(db)
    db.refresh(s)
    return _present(db, [s])[0]

@router.post("/scenarios/{sid}/validate", response_model=ScenarioValidationReport)
def validate_saved_scenario(sid: int, db: Session = Depends(get_db)):
    return _validate(db, get_scenario_or_404(db, sid))


@router.post("/scenarios/{sid}/finalize", response_model=ScenarioOut)
def finalize_scenario(sid: int, db: Session = Depends(get_db)):
    s = get_scenario_or_404(db, sid)
    if s.status != "final":
        report = _validate(db, s)
        if not report["valid"]:
            first = next(i["message"] for i in report["issues"] if i["level"] == "error")
            raise HTTPException(422, f"Cannot finalize: {report['error_count']} error(s). First: {first}")
        s.status = "final"
        touch(s)
        commit(db)
        db.refresh(s)
    return _present(db, [s])[0]


@router.post("/scenarios/{sid}/new-version", response_model=ScenarioOut, status_code=201)
def new_version(sid: int, db: Session = Depends(get_db)):
    src = get_scenario_or_404(db, sid)
    latest = db.scalar(select(func.max(Scenario.version)).where(
        Scenario.environment_id == src.environment_id, Scenario.name == src.name)) or src.version
    new = Scenario(environment_id=src.environment_id, parent_id=src.id, name=src.name,
                   version=latest + 1, description=src.description,
                   assumptions=copy.deepcopy(src.assumptions),
                   modifications=copy.deepcopy(src.modifications or []), status="draft")
    db.add(new)
    db.flush()
    _clone_events(db, src.id, new.id)
    commit(db)
    db.refresh(new)
    return _present(db, [new])[0]


@router.post("/scenarios/{sid}/duplicate", response_model=ScenarioOut, status_code=201)
def duplicate_scenario(sid: int, db: Session = Depends(get_db)):
    src = get_scenario_or_404(db, sid)
    dup = Scenario(environment_id=src.environment_id,
                   name=_free_copy_name(db, src.environment_id, src.name), version=1,
                   description=src.description, assumptions=copy.deepcopy(src.assumptions),
                   modifications=copy.deepcopy(src.modifications or []), status="draft")
    db.add(dup)
    db.flush()
    _clone_events(db, src.id, dup.id)
    commit(db)
    db.refresh(dup)
    return _present(db, [dup])[0]


@router.post("/scenarios/{sid}/archive", response_model=ScenarioOut)
def archive_scenario(sid: int, db: Session = Depends(get_db)):
    s = get_scenario_or_404(db, sid)
    s.is_archived = True
    commit(db)
    db.refresh(s)
    return _present(db, [s])[0]


@router.post("/scenarios/{sid}/unarchive", response_model=ScenarioOut)
def unarchive_scenario(sid: int, db: Session = Depends(get_db)):
    s = get_scenario_or_404(db, sid)
    s.is_archived = False
    commit(db)
    db.refresh(s)
    return _present(db, [s])[0]


@router.delete("/scenarios/{sid}", status_code=204)
def delete_scenario(sid: int, force: bool = False, db: Session = Depends(get_db)):
    s = get_scenario_or_404(db, sid)
    n = db.scalar(select(func.count(Simulation.id)).where(Simulation.scenario_id == sid)) or 0
    if n and not force:
        raise HTTPException(409, f"This scenario has {n} saved simulation(s). "
                                 "Deleting it also deletes them; confirm to proceed.")
    db.delete(s)  # the database cascades to events and simulations
    commit(db)


# ---------- samples ----------
@router.post("/environments/{env_id}/demo-scenarios", response_model=list[ScenarioOut], status_code=201)
def add_sample_scenarios(env_id: int, db: Session = Depends(get_db)):
    get_env_or_404(db, env_id)
    nodes = {n.name: n.id for n in db.scalars(select(Node).where(Node.environment_id == env_id))}
    needed = {ev["target"] for spec in SAMPLE_SCENARIOS for ev in spec["events"]}
    missing = sorted(needed - set(nodes))
    if missing:
        raise HTTPException(409, "This environment does not contain the nodes the samples need: "
                                 f"{', '.join(missing)}. Load the NEXUS Campus demo (or a copy of it) first.")
    existing = {n.lower() for n in db.scalars(select(Scenario.name).where(Scenario.environment_id == env_id))}
    created: list[Scenario] = []
    for spec in SAMPLE_SCENARIOS:
        if spec["name"].lower() in existing:
            continue
        s = Scenario(environment_id=env_id, name=spec["name"], description=spec["description"],
                     assumptions=list(spec["assumptions"]), status="draft", version=1)
        db.add(s)
        db.flush()
        for ev in spec["events"]:
            db.add(ScenarioEvent(scenario_id=s.id, event_type=ev["event_type"],
                                 target_node_id=nodes[ev["target"]], params=dict(ev["params"]),
                                 start_time=ev["start_time"], duration=ev["duration"]))
        db.flush()
        if _validate(db, s)["valid"]:
            s.status = "final"
        created.append(s)
    if not created:
        raise HTTPException(409, "The sample scenarios are already present in this environment.")
    commit(db)
    for s in created:
        db.refresh(s)
    return _present(db, created)