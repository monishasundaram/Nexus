import json
from datetime import datetime
from typing import Annotated, Literal

from pydantic import (AfterValidator, BaseModel, ConfigDict, Field,
                      StringConstraints, model_validator)

Category = Literal["building", "road", "electricity", "water", "drainage",
                   "transport", "communication", "generic"]
State = Literal["operational", "degraded", "failed", "maintenance"]
Relationship = Literal["required", "partial", "backup"]

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Text = Annotated[str, Field(max_length=2000)]
Coord = Annotated[float, Field(ge=-1e6, le=1e6)]
Amount = Annotated[float, Field(ge=0, le=1e9)]
Unit = Annotated[float, Field(ge=0, le=1)]
Lat = Annotated[float, Field(ge=-90, le=90)]
Lon = Annotated[float, Field(ge=-180, le=180)]


def _check_meta(value: dict) -> dict:
    if len(json.dumps(value)) > 10_000:
        raise ValueError("metadata is too large (max 10 KB)")
    return value


Meta = Annotated[dict, AfterValidator(_check_meta)]


# ---------- nodes ----------
class NodeCreate(BaseModel):
    name: Name
    category: Category = "generic"
    description: Text = ""
    pos_x: Coord = 0
    pos_y: Coord = 0
    state: State = "operational"
    capacity: Amount = 0
    demand: Amount = 0
    importance: Unit = 0.5
    latitude: Lat | None = None
    longitude: Lon | None = None
    meta: Meta = Field(default_factory=dict)


class NodeUpdate(BaseModel):
    name: Name | None = None
    category: Category | None = None
    description: Text | None = None
    pos_x: Coord | None = None
    pos_y: Coord | None = None
    state: State | None = None
    capacity: Amount | None = None
    demand: Amount | None = None
    importance: Unit | None = None
    latitude: Lat | None = None
    longitude: Lon | None = None
    meta: Meta | None = None


class NodeOut(NodeCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    environment_id: int


# ---------- edges ----------
class EdgeCreate(BaseModel):
    source_id: int
    destination_id: int
    relationship_type: Relationship = "required"
    strength: Unit = 1.0
    capacity: Amount | None = None
    description: Text = ""
    meta: Meta = Field(default_factory=dict)

    @model_validator(mode="after")
    def no_self_loop(self):
        if self.source_id == self.destination_id:
            raise ValueError("A node cannot depend on itself")
        return self


class EdgeUpdate(BaseModel):
    relationship_type: Relationship | None = None
    strength: Unit | None = None
    capacity: Amount | None = None
    description: Text | None = None
    meta: Meta | None = None


class EdgeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    environment_id: int
    source_id: int
    destination_id: int
    relationship_type: Relationship
    strength: float
    capacity: float | None
    description: str
    meta: dict


# ---------- environments ----------
class EnvironmentCreate(BaseModel):
    name: Name
    description: Text = ""


class EnvironmentUpdate(BaseModel):
    name: Name | None = None
    description: Text | None = None


class EnvironmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: int
    name: str
    description: str
    model_version: str
    is_demo: bool
    created_at: datetime
    updated_at: datetime
    node_count: int = 0
    edge_count: int = 0


class EnvironmentDetail(EnvironmentOut):
    nodes: list[NodeOut] = Field(default_factory=list)
    edges: list[EdgeOut] = Field(default_factory=list)


# ---------- validation ----------
class ValidationIssue(BaseModel):
    level: Literal["error", "warning", "info"]
    code: str
    message: str
    node_ids: list[int]
    edge_ids: list[int]


class ValidationReport(BaseModel):
    valid: bool
    error_count: int
    warning_count: int
    issues: list[ValidationIssue]
    stats: dict