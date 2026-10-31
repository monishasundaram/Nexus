from datetime import datetime, timezone
from sqlalchemy import (JSON, Boolean, CheckConstraint, DateTime, Float,
                        ForeignKey, Index, Integer, String, Text, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base

def utcnow():
    return datetime.now(timezone.utc)

class Stamps:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

class Project(Stamps, Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")

class Environment(Stamps, Base):
    __tablename__ = "environments"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    model_version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

class Node(Stamps, Base):
    __tablename__ = "nodes"
    __table_args__ = (
        UniqueConstraint("environment_id", "name"),
        CheckConstraint("capacity >= 0"), CheckConstraint("demand >= 0"),
        CheckConstraint("importance >= 0 AND importance <= 1"),
        CheckConstraint("state IN ('operational','degraded','failed','maintenance')"),
        CheckConstraint("category IN ('building','road','electricity','water','drainage',"
                        "'transport','communication','generic')"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    environment_id: Mapped[int] = mapped_column(ForeignKey("environments.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(30))
    description: Mapped[str] = mapped_column(Text, default="")
    pos_x: Mapped[float] = mapped_column(Float, default=0)
    pos_y: Mapped[float] = mapped_column(Float, default=0)
    state: Mapped[str] = mapped_column(String(20), default="operational")
    capacity: Mapped[float] = mapped_column(Float, default=0)
    demand: Mapped[float] = mapped_column(Float, default=0)
    importance: Mapped[float] = mapped_column(Float, default=0.5)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)  # "metadata" is reserved by SQLAlchemy

class Edge(Stamps, Base):
    __tablename__ = "edges"
    __table_args__ = (
        UniqueConstraint("environment_id", "source_id", "destination_id", "relationship_type"),
        CheckConstraint("source_id != destination_id"),
        CheckConstraint("strength >= 0 AND strength <= 1"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    environment_id: Mapped[int] = mapped_column(ForeignKey("environments.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("nodes.id", ondelete="CASCADE"), index=True)
    destination_id: Mapped[int] = mapped_column(ForeignKey("nodes.id", ondelete="CASCADE"), index=True)
    relationship_type: Mapped[str] = mapped_column(String(30), default="required")
    strength: Mapped[float] = mapped_column(Float, default=1.0)
    capacity: Mapped[float | None] = mapped_column(Float, nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

class Scenario(Stamps, Base):
    __tablename__ = "scenarios"
    __table_args__ = (UniqueConstraint("environment_id", "name", "version"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    environment_id: Mapped[int] = mapped_column(ForeignKey("environments.id", ondelete="CASCADE"), index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("scenarios.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(120))
    version: Mapped[int] = mapped_column(Integer, default=1)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="draft")
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    assumptions: Mapped[list] = mapped_column(JSON, default=list)

class ScenarioEvent(Base):
    __tablename__ = "scenario_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    scenario_id: Mapped[int] = mapped_column(ForeignKey("scenarios.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(30))
    target_node_id: Mapped[int | None] = mapped_column(ForeignKey("nodes.id", ondelete="SET NULL"), nullable=True)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    start_time: Mapped[float] = mapped_column(Float, default=0)
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)

class Simulation(Base):
    __tablename__ = "simulations"
    id: Mapped[int] = mapped_column(primary_key=True)
    scenario_id: Mapped[int] = mapped_column(ForeignKey("scenarios.id", ondelete="CASCADE"), index=True)
    scenario_version: Mapped[int] = mapped_column(Integer)
    baseline_snapshot: Mapped[dict] = mapped_column(JSON)  # frozen copy of nodes + edges
    model_version: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="queued")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

class SimulationResult(Base):
    __tablename__ = "simulation_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    simulation_id: Mapped[int] = mapped_column(ForeignKey("simulations.id", ondelete="CASCADE"), unique=True)
    node_results: Mapped[list] = mapped_column(JSON, default=list)
    aggregate_metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    dependency_traces: Mapped[list] = mapped_column(JSON, default=list)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    assumptions: Mapped[list] = mapped_column(JSON, default=list)

class Report(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    simulation_id: Mapped[int] = mapped_column(ForeignKey("simulations.id", ondelete="CASCADE"), index=True)
    format: Mapped[str] = mapped_column(String(10))
    storage_ref: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class AIExplanation(Base):
    __tablename__ = "ai_explanations"
    id: Mapped[int] = mapped_column(primary_key=True)
    simulation_id: Mapped[int] = mapped_column(ForeignKey("simulations.id", ondelete="CASCADE"), index=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    source_refs: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)