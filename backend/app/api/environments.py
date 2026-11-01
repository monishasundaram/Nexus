import copy

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import MODEL_VERSION
from ..database import get_db
from ..engine.validation import validate_graph
from ..models import Edge, Environment, Node
from ..schemas import (EdgeOut, EnvironmentCreate, EnvironmentDetail, EnvironmentOut,
                       EnvironmentUpdate, NodeOut, ValidationReport)
from ..seed.campus import CAMPUS_NAME, load_campus
from ..services import get_default_project
from .common import apply_patch, commit, get_env_or_404, load_graph

router = APIRouter()

NODE_FIELDS = ["name", "category", "description", "pos_x", "pos_y", "state", "capacity",
               "demand", "importance", "latitude", "longitude", "meta"]
EDGE_FIELDS = ["relationship_type", "strength", "capacity", "description", "meta"]


def _out(db: Session, env: Environment) -> EnvironmentOut:
    out = EnvironmentOut.model_validate(env)
    out.node_count = db.scalar(select(func.count(Node.id)).where(Node.environment_id == env.id)) or 0
    out.edge_count = db.scalar(select(func.count(Edge.id)).where(Edge.environment_id == env.id)) or 0
    return out


@router.get("/environments", response_model=list[EnvironmentOut])
def list_environments(db: Session = Depends(get_db)):
    envs = db.scalars(select(Environment).order_by(Environment.updated_at.desc())).all()
    nc = {r[0]: r[1] for r in db.execute(select(Node.environment_id, func.count()).group_by(Node.environment_id))}
    ec = {r[0]: r[1] for r in db.execute(select(Edge.environment_id, func.count()).group_by(Edge.environment_id))}
    result = []
    for env in envs:
        out = EnvironmentOut.model_validate(env)
        out.node_count, out.edge_count = nc.get(env.id, 0), ec.get(env.id, 0)
        result.append(out)
    return result


@router.post("/environments", response_model=EnvironmentOut, status_code=201)
def create_environment(body: EnvironmentCreate, db: Session = Depends(get_db)):
    project = get_default_project(db)
    env = Environment(project_id=project.id, name=body.name, description=body.description,
                      model_version=MODEL_VERSION)
    db.add(env)
    commit(db)
    db.refresh(env)
    return _out(db, env)


@router.get("/environments/{env_id}", response_model=EnvironmentDetail)
def get_environment(env_id: int, db: Session = Depends(get_db)):
    env = get_env_or_404(db, env_id)
    nodes, edges = load_graph(db, env_id)
    detail = EnvironmentDetail.model_validate(env)
    detail.nodes = [NodeOut.model_validate(n) for n in nodes]
    detail.edges = [EdgeOut.model_validate(e) for e in edges]
    detail.node_count, detail.edge_count = len(nodes), len(edges)
    return detail


@router.patch("/environments/{env_id}", response_model=EnvironmentOut)
def update_environment(env_id: int, body: EnvironmentUpdate, db: Session = Depends(get_db)):
    env = get_env_or_404(db, env_id)
    apply_patch(env, body.model_dump(exclude_unset=True))
    commit(db)
    db.refresh(env)
    return _out(db, env)


@router.delete("/environments/{env_id}", status_code=204)
def delete_environment(env_id: int, db: Session = Depends(get_db)):
    env = get_env_or_404(db, env_id)
    db.delete(env)  # the database cascades to nodes, edges, scenarios, simulations
    commit(db)


@router.post("/environments/{env_id}/duplicate", response_model=EnvironmentOut, status_code=201)
def duplicate_environment(env_id: int, db: Session = Depends(get_db)):
    src = get_env_or_404(db, env_id)
    dup = Environment(project_id=src.project_id, name=f"{src.name} (copy)"[:120],
                      description=src.description, model_version=src.model_version, is_demo=False)
    db.add(dup)
    db.flush()
    nodes, edges = load_graph(db, src.id)
    mapping: dict[int, int] = {}
    for n in nodes:
        c = Node(environment_id=dup.id, **{f: copy.deepcopy(getattr(n, f)) for f in NODE_FIELDS})
        db.add(c)
        db.flush()
        mapping[n.id] = c.id
    for e in edges:
        db.add(Edge(environment_id=dup.id, source_id=mapping[e.source_id],
                    destination_id=mapping[e.destination_id],
                    **{f: copy.deepcopy(getattr(e, f)) for f in EDGE_FIELDS}))
    commit(db)
    db.refresh(dup)
    return _out(db, dup)


@router.post("/environments/{env_id}/validate", response_model=ValidationReport)
def validate_environment(env_id: int, db: Session = Depends(get_db)):
    get_env_or_404(db, env_id)
    nodes, edges = load_graph(db, env_id)
    return validate_graph(
        [{"id": n.id, "name": n.name, "category": n.category, "state": n.state,
          "capacity": n.capacity, "demand": n.demand, "importance": n.importance} for n in nodes],
        [{"id": e.id, "source_id": e.source_id, "destination_id": e.destination_id,
          "relationship_type": e.relationship_type, "strength": e.strength,
          "capacity": e.capacity} for e in edges])


@router.post("/demo/campus", response_model=EnvironmentOut, status_code=201)
def load_demo_campus(db: Session = Depends(get_db)):
    existing = db.scalar(select(Environment.id).where(Environment.is_demo.is_(True),
                                                      Environment.name == CAMPUS_NAME))
    if existing:
        raise HTTPException(409, "NEXUS Campus is already loaded. Duplicate it for a fresh editable copy.")
    env = load_campus(db)
    commit(db)
    db.refresh(env)
    return _out(db, env)