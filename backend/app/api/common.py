from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import Edge, Environment, Node, utcnow


def get_env_or_404(db: Session, env_id: int) -> Environment:
    env = db.get(Environment, env_id)
    if env is None:
        raise HTTPException(404, "Environment not found")
    return env


def get_node_or_404(db: Session, node_id: int) -> Node:
    node = db.get(Node, node_id)
    if node is None:
        raise HTTPException(404, "Node not found")
    return node


def get_edge_or_404(db: Session, edge_id: int) -> Edge:
    edge = db.get(Edge, edge_id)
    if edge is None:
        raise HTTPException(404, "Connection not found")
    return edge


def load_graph(db: Session, env_id: int):
    nodes = db.scalars(select(Node).where(Node.environment_id == env_id).order_by(Node.id)).all()
    edges = db.scalars(select(Edge).where(Edge.environment_id == env_id).order_by(Edge.id)).all()
    return nodes, edges


def touch(env: Environment | None) -> None:
    if env is not None:
        env.updated_at = utcnow()


def apply_patch(obj, data: dict, nullable: tuple[str, ...] = ()) -> None:
    for key, value in data.items():
        if value is None and key not in nullable:
            continue
        setattr(obj, key, value)


def commit(db: Session, message: str = "That change conflicts with existing data.") -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, message)