from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import MAX_EDGES, MAX_NODES
from ..database import get_db
from ..models import Edge, Environment, Node
from ..schemas import EdgeCreate, EdgeOut, EdgeUpdate, NodeCreate, NodeOut, NodeUpdate
from .common import (apply_patch, commit, get_edge_or_404, get_env_or_404,
                     get_node_or_404, touch)

router = APIRouter()


def _ensure_unique_name(db: Session, env_id: int, name: str, exclude_id: int | None = None):
    q = select(Node.id).where(Node.environment_id == env_id,
                              func.lower(Node.name) == name.strip().lower())
    if exclude_id is not None:
        q = q.where(Node.id != exclude_id)
    if db.scalar(q) is not None:
        raise HTTPException(409, f"A node named '{name}' already exists in this environment.")


# ---------- nodes ----------
@router.post("/environments/{env_id}/nodes", response_model=NodeOut, status_code=201)
def create_node(env_id: int, body: NodeCreate, db: Session = Depends(get_db)):
    env = get_env_or_404(db, env_id)
    count = db.scalar(select(func.count(Node.id)).where(Node.environment_id == env_id)) or 0
    if count >= MAX_NODES:
        raise HTTPException(422, f"An environment is limited to {MAX_NODES} nodes.")
    _ensure_unique_name(db, env_id, body.name)
    node = Node(environment_id=env_id, **body.model_dump())
    db.add(node)
    touch(env)
    commit(db)
    db.refresh(node)
    return node


@router.patch("/nodes/{node_id}", response_model=NodeOut)
def update_node(node_id: int, body: NodeUpdate, db: Session = Depends(get_db)):
    node = get_node_or_404(db, node_id)
    data = body.model_dump(exclude_unset=True)
    if data.get("name") is not None:
        _ensure_unique_name(db, node.environment_id, data["name"], exclude_id=node.id)
    apply_patch(node, data, nullable=("latitude", "longitude"))
    touch(db.get(Environment, node.environment_id))
    commit(db)
    db.refresh(node)
    return node


@router.delete("/nodes/{node_id}", status_code=204)
def delete_node(node_id: int, db: Session = Depends(get_db)):
    node = get_node_or_404(db, node_id)
    touch(db.get(Environment, node.environment_id))
    db.delete(node)  # connected edges are removed by the database cascade
    commit(db)


# ---------- edges ----------
@router.post("/environments/{env_id}/edges", response_model=EdgeOut, status_code=201)
def create_edge(env_id: int, body: EdgeCreate, db: Session = Depends(get_db)):
    env = get_env_or_404(db, env_id)
    count = db.scalar(select(func.count(Edge.id)).where(Edge.environment_id == env_id)) or 0
    if count >= MAX_EDGES:
        raise HTTPException(422, f"An environment is limited to {MAX_EDGES} connections.")
    for label, nid in (("source", body.source_id), ("destination", body.destination_id)):
        node = db.get(Node, nid)
        if node is None or node.environment_id != env_id:
            raise HTTPException(422, f"The {label} node ({nid}) does not exist in this environment.")
    duplicate = db.scalar(select(Edge.id).where(
        Edge.environment_id == env_id, Edge.source_id == body.source_id,
        Edge.destination_id == body.destination_id,
        Edge.relationship_type == body.relationship_type))
    if duplicate is not None:
        raise HTTPException(409, "That connection already exists.")
    edge = Edge(environment_id=env_id, **body.model_dump())
    db.add(edge)
    touch(env)
    commit(db)
    db.refresh(edge)
    return edge


@router.patch("/edges/{edge_id}", response_model=EdgeOut)
def update_edge(edge_id: int, body: EdgeUpdate, db: Session = Depends(get_db)):
    edge = get_edge_or_404(db, edge_id)
    apply_patch(edge, body.model_dump(exclude_unset=True), nullable=("capacity",))
    touch(db.get(Environment, edge.environment_id))
    commit(db, "A connection of that type already exists between these nodes.")
    db.refresh(edge)
    return edge


@router.delete("/edges/{edge_id}", status_code=204)
def delete_edge(edge_id: int, db: Session = Depends(get_db)):
    edge = get_edge_or_404(db, edge_id)
    touch(db.get(Environment, edge.environment_id))
    db.delete(edge)
    commit(db)