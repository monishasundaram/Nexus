from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Environment, Node, Scenario, Simulation

router = APIRouter()

@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    recent = db.scalars(select(Simulation).order_by(Simulation.started_at.desc()).limit(5)).all()
    categories = db.execute(select(Node.category, func.count()).group_by(Node.category)).all()
    return {
        "environments": db.scalar(select(func.count(Environment.id))),
        "scenarios": db.scalar(select(func.count(Scenario.id))),
        "completed_simulations": db.scalar(
            select(func.count(Simulation.id)).where(Simulation.status == "completed")),
        "recent_simulations": [
            {"id": s.id, "scenario_id": s.scenario_id, "status": s.status,
             "started_at": s.started_at.isoformat()} for s in recent],
        "category_distribution": [{"category": c, "count": n} for c, n in categories],
        "most_affected_nodes": [],  # filled in once simulations exist (Phase 5)
    }