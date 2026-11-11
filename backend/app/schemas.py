import json
from datetime import datetime
from .engine.events import check_event_shape
from typing import Annotated, Literal, Union

from pydantic import (AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field,
                      StringConstraints, model_validator)

from .config import MAX_EVENTS, MAX_MODIFICATIONS, MAX_TIME

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

# ---------- scenarios ----------
EventType = Literal["failure", "capacity_reduction", "road_closure",
                    "resource_shortage", "maintenance", "recovery"]
Hours = Annotated[float, Field(ge=0, le=MAX_TIME)]
PositiveHours = Annotated[float, Field(gt=0, le=MAX_TIME)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class EventIn(BaseModel):
    event_type: EventType
    target_node_id: int
    params: dict = Field(default_factory=dict)
    start_time: Hours = 0
    duration: PositiveHours | None = None

    @model_validator(mode="after")
    def check_shape(self):
        problems = check_event_shape(self.event_type, self.params, self.duration)
        if problems:
            raise ValueError(" ".join(problems))
        return self


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    event_type: str
    target_node_id: int | None
    params: dict
    start_time: float
    duration: float | None


class ScenarioIn(BaseModel):
    name: Name
    description: Text = ""
    assumptions: list[ShortText] = Field(default_factory=list, max_length=20)
    events: list[EventIn] = Field(default_factory=list, max_length=MAX_EVENTS)


class ScenarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    environment_id: int
    parent_id: int | None
    name: str
    version: int
    description: str
    status: str
    is_archived: bool
    assumptions: list[str]
    created_at: datetime
    updated_at: datetime
    events: list[EventOut] = Field(default_factory=list)
    simulation_count: int = 0
    environment_name: str = ""
    modifications: Annotated[list[dict], BeforeValidator(lambda v: v or [])] = Field(default_factory=list)
    modification_labels: list[str] = Field(default_factory=list)


class ScenarioIssue(BaseModel):
    level: Literal["error", "warning", "info"]
    code: str
    message: str
    node_ids: list[int]
    event_ids: list[int]


class ScenarioValidationReport(BaseModel):
    valid: bool
    error_count: int
    warning_count: int
    issues: list[ScenarioIssue]
    stats: dict



# ---------- intervention modifications ----------
class _Mod(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SetCapacityMod(_Mod):
    type: Literal["set_capacity"]
    node_id: int
    capacity: Amount


class ReduceDemandMod(_Mod):
    type: Literal["reduce_demand"]
    node_id: int
    reduce_pct: Annotated[float, Field(gt=0, le=100)]


class AddNodeMod(_Mod):
    type: Literal["add_node"]
    key: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{1,40}$")]
    name: Name
    category: Category
    capacity: Amount = 0
    importance: Unit = 0.5
    unit: Annotated[str, StringConstraints(strip_whitespace=True, max_length=20)] = ""


class AddEdgeMod(_Mod):
    type: Literal["add_edge"]
    source: int | str
    destination: int | str
    relationship_type: Relationship = "required"
    strength: Unit = 1.0


class SetEdgeMod(_Mod):
    type: Literal["set_edge"]
    edge_id: int
    strength: Unit | None = None
    relationship_type: Relationship | None = None

    @model_validator(mode="after")
    def something_changes(self):
        if self.strength is None and self.relationship_type is None:
            raise ValueError("Give a new strength, a new type, or both")
        return self


Modification = Annotated[
    Union[SetCapacityMod, ReduceDemandMod, AddNodeMod, AddEdgeMod, SetEdgeMod], Field(discriminator="type")]


class ModificationsIn(BaseModel):
    modifications: list[Modification] = Field(default_factory=list, max_length=MAX_MODIFICATIONS)


# ---------- comparisons ----------
class ComparisonIn(BaseModel):
    simulation_ids: list[int] = Field(min_length=2, max_length=6)