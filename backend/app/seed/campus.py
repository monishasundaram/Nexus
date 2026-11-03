"""NEXUS Campus: a synthetic demonstration environment (not real infrastructure)."""
from sqlalchemy.orm import Session

from ..config import MODEL_VERSION
from ..models import Edge, Environment, Node
from ..services import get_default_project

CAMPUS_NAME = "NEXUS Campus"


def _n(name, cat, x, y, cap=0, dem=0, imp=0.5, unit="", demands=None, desc=""):
    # capacity/demand share the node's own `unit`.
    # meta.demands = what this node needs from its suppliers (used by the Phase 4 engine).
    return dict(name=name, category=cat, pos_x=x, pos_y=y, capacity=cap, demand=dem,
                importance=imp, description=desc,
                meta={"synthetic": True, "unit": unit, "demands": demands or {}})


CAMPUS_NODES = [
    # Electricity
    _n("Primary Grid Supply", "electricity", 0, 0, 1000, 0, 1.0, "kW", desc="Main utility electricity feed."),
    _n("Backup Diesel Generator", "electricity", 0, 140, 400, 0, 0.6, "kW", desc="Standby generator (synthetic capacity)."),
    _n("Main Substation", "electricity", 260, 70, 1000, 0, 0.9, "kW", desc="Distributes power across campus."),
    # Water
    _n("Municipal Water Supply", "water", 0, 340, 500, 0, 1.0, "kL/day", desc="External water main."),
    _n("Water Pump House", "water", 520, 260, 500, 0, 0.8, "kL/day", demands={"electricity": 60}, desc="Electric pumps lifting water to the tank."),
    _n("Overhead Water Tank", "water", 780, 260, 400, 0, 0.7, "kL/day", desc="Storage and gravity distribution."),
    # Drainage
    _n("Drainage Network", "drainage", 520, 400, 300, 0, 0.6, "kL/day", demands={"electricity": 20}, desc="Storm and waste water drainage."),
    # Communication
    _n("Campus Network Hub", "communication", 520, 0, 10, 0, 0.8, "Gbps", demands={"electricity": 30}, desc="Core network and Wi-Fi."),
    # Roads and transport
    _n("Main Gate Road", "road", 0, 640, 600, 0, 0.9, "veh/h", desc="Primary campus entrance."),
    _n("Central Avenue", "road", 520, 560, 600, 0, 0.9, "veh/h", desc="Spine road serving the academic blocks."),
    _n("North Service Road", "road", 520, 700, 300, 0, 0.5, "veh/h", desc="Service and hostel access."),
    _n("East Ring Road", "road", 520, 840, 300, 0, 0.5, "veh/h", desc="Alternate ring route."),
    _n("Campus Shuttle Route", "transport", 780, 700, 200, 0, 0.6, "passengers/h", desc="Internal shuttle service."),
    # Buildings: demand = electricity (kW); water need is in meta.demands
    _n("Administration Building", "building", 1060, 0, 0, 50, 0.7, "kW", {"electricity": 50, "water": 20}),
    _n("Central Library", "building", 1060, 95, 0, 70, 0.6, "kW", {"electricity": 70, "water": 15}),
    _n("Science Block", "building", 1060, 190, 0, 150, 0.8, "kW", {"electricity": 150, "water": 60}),
    _n("Engineering Block", "building", 1060, 285, 0, 130, 0.7, "kW", {"electricity": 130, "water": 40}),
    _n("Lecture Hall Complex", "building", 1060, 380, 0, 80, 0.6, "kW", {"electricity": 80, "water": 25}),
    _n("Hostel Block A", "building", 1060, 475, 0, 90, 0.8, "kW", {"electricity": 90, "water": 90}),
    _n("Cafeteria", "building", 1060, 570, 0, 60, 0.5, "kW", {"electricity": 60, "water": 50}),
    _n("Health Center", "building", 1060, 665, 0, 50, 0.9, "kW", {"electricity": 50, "water": 30}),
]

BUILDINGS = [n["name"] for n in CAMPUS_NODES if n["category"] == "building"]
_WATER_REQUIRED = {"Science Block", "Hostel Block A", "Cafeteria", "Health Center"}

# (supplier, dependent, relationship, strength): the dependent needs the supplier
CAMPUS_EDGES = [
    ("Primary Grid Supply", "Main Substation", "required", 1.0),
    ("Backup Diesel Generator", "Main Substation", "backup", 0.8),
    ("Municipal Water Supply", "Water Pump House", "required", 1.0),
    ("Water Pump House", "Overhead Water Tank", "required", 1.0),
    ("Main Gate Road", "Central Avenue", "required", 1.0),
    ("Main Gate Road", "North Service Road", "required", 1.0),
    ("Main Gate Road", "East Ring Road", "required", 1.0),
    ("Central Avenue", "Campus Shuttle Route", "required", 1.0),
    ("East Ring Road", "Campus Shuttle Route", "backup", 0.7),
    ("Main Substation", "Water Pump House", "required", 1.0),
    ("Main Substation", "Campus Network Hub", "required", 1.0),
    ("Main Substation", "Drainage Network", "partial", 0.5),
]
for _b in BUILDINGS:
    CAMPUS_EDGES.append(("Main Substation", _b, "required", 1.0))
    CAMPUS_EDGES.append(("Overhead Water Tank", _b,
                         "required" if _b in _WATER_REQUIRED else "partial",
                         1.0 if _b in _WATER_REQUIRED else 0.4))

_PARTIAL = {
    "Drainage Network": {"Hostel Block A": 0.5, "Cafeteria": 0.5, "Science Block": 0.4, "Health Center": 0.5},
    "Campus Network Hub": {"Administration Building": 0.6, "Central Library": 0.5, "Engineering Block": 0.5,
                           "Science Block": 0.4, "Lecture Hall Complex": 0.4, "Health Center": 0.4},
    "Central Avenue": {"Administration Building": 0.5, "Central Library": 0.5, "Science Block": 0.5,
                       "Engineering Block": 0.5, "Lecture Hall Complex": 0.6, "Cafeteria": 0.4},
    "North Service Road": {"Hostel Block A": 0.6, "Cafeteria": 0.4, "Health Center": 0.6},
    "Campus Shuttle Route": {"Hostel Block A": 0.4, "Engineering Block": 0.3, "Lecture Hall Complex": 0.3},
}
for _src, _targets in _PARTIAL.items():
    for _dst, _s in _targets.items():
        CAMPUS_EDGES.append((_src, _dst, "partial", _s))


def load_campus(db: Session) -> Environment:
    project = get_default_project(db)
    env = Environment(
        project_id=project.id, name=CAMPUS_NAME, model_version=MODEL_VERSION, is_demo=True,
        description="Synthetic demonstration environment. All values are simulated demo data, "
                    "not real infrastructure.")
    db.add(env)
    db.flush()
    ids: dict[str, int] = {}
    for spec in CAMPUS_NODES:
        node = Node(environment_id=env.id, **spec)
        db.add(node)
        db.flush()
        ids[spec["name"]] = node.id
    for src, dst, rel, strength in CAMPUS_EDGES:
        db.add(Edge(environment_id=env.id, source_id=ids[src], destination_id=ids[dst],
                    relationship_type=rel, strength=strength))
    db.flush()
    return env