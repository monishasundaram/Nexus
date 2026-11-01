"""Event types and shape rules. Pure Python: no web framework or database imports."""
from math import inf


def _t(label, description, param=None, param_label=None, duration="optional", targets=None):
    return {"label": label, "description": description, "param": param,
            "param_label": param_label, "duration": duration, "targets": targets}


EVENT_TYPES: dict[str, dict] = {
    "failure": _t("Infrastructure failure",
                  "The target stops working completely (capacity 0) while the event is active."),
    "capacity_reduction": _t("Capacity reduction",
                             "The target's capacity is reduced by a percentage.",
                             "reduction_pct", "Reduction (%)"),
    "road_closure": _t("Road closure",
                       "A road is closed to traffic, treated as a full outage of that road node.",
                       targets=["road"]),
    "resource_shortage": _t("Resource shortage",
                            "A supply node delivers less than its normal capacity.",
                            "shortage_pct", "Shortage (%)",
                            targets=["electricity", "water", "communication", "generic"]),
    "maintenance": _t("Temporary maintenance",
                      "The target is offline for a planned period.", duration="required"),
    "recovery": _t("Recovery / restoration",
                   "The target returns to operational with its baseline capacity.",
                   duration="forbidden"),
}

DISRUPTIONS = {"failure", "capacity_reduction", "road_closure", "resource_shortage", "maintenance"}


def check_event_shape(event_type: str, params: dict, duration: float | None) -> list[str]:
    """Return a list of problems (empty list = the event is well-formed)."""
    spec = EVENT_TYPES.get(event_type)
    if spec is None:
        return [f"Unknown event type '{event_type}'."]
    problems: list[str] = []
    allowed = {spec["param"]} if spec["param"] else set()
    extra = set(params) - allowed
    if extra:
        problems.append(f"Unexpected parameter(s): {', '.join(sorted(extra))}.")
    if spec["param"]:
        value = params.get(spec["param"])
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            problems.append(f"'{spec['param']}' is required and must be a number.")
        elif not 0 < value <= 100:
            problems.append(f"'{spec['param']}' must be above 0 and at most 100.")
    if spec["duration"] == "required" and duration is None:
        problems.append("A duration is required for this event type.")
    if spec["duration"] == "forbidden" and duration is not None:
        problems.append("This event type cannot have a duration.")
    return problems


def event_window(start: float, duration: float | None) -> tuple[float, float]:
    """Half-open interval [start, end) during which an event is active."""
    return start, inf if duration is None else start + duration