from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Project


def get_default_project(db: Session) -> Project:
    project = db.scalar(select(Project).order_by(Project.id).limit(1))
    if project is None:
        project = Project(name="Default Project", description="Created automatically")
        db.add(project)
        db.flush()
    return project