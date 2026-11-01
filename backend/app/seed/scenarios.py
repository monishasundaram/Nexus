"""Sample scenarios for NEXUS Campus (synthetic demonstration). Outcomes come from the engine, not from here."""

_SYNTHETIC = "NEXUS Campus is synthetic demonstration data, not real infrastructure."
_WHOLE_RUN = "The event starts at t=0 and lasts for the whole simulation (no duration is set)."


def _ev(kind, target, params=None, start=0.0, duration=None):
    return {"event_type": kind, "target": target, "params": params or {},
            "start_time": start, "duration": duration}


SAMPLE_SCENARIOS = [
    {
        "name": "Primary electricity supply failure",
        "description": "The primary grid feed to the campus fails at t=0.",
        "assumptions": [_SYNTHETIC, _WHOLE_RUN,
                        "The backup diesel generator is modelled as a backup supplier of the Main Substation. "
                        "Whether it covers demand is calculated by the engine."],
        "events": [_ev("failure", "Primary Grid Supply")],
    },
    {
        "name": "Water supply capacity reduced by 50%",
        "description": "The municipal water main delivers half of its normal capacity from t=0.",
        "assumptions": [_SYNTHETIC, _WHOLE_RUN,
                        "Capacity is reduced to 50% of its baseline value; there is no alternative water source."],
        "events": [_ev("capacity_reduction", "Municipal Water Supply", {"reduction_pct": 50})],
    },
    {
        "name": "Critical campus road closure",
        "description": "Central Avenue, the spine road serving the academic blocks, is closed from t=0.",
        "assumptions": [_SYNTHETIC, _WHOLE_RUN,
                        "A closed road is treated as a full outage of that road node."],
        "events": [_ev("road_closure", "Central Avenue")],
    },
    {
        "name": "Combined disruption",
        "description": "The primary grid fails, the water supply drops by 50%, and Central Avenue closes, all at t=0.",
        "assumptions": [_SYNTHETIC, "All three events start together and last for the whole simulation.",
                        "Effects on different nodes are independent until the engine propagates them."],
        "events": [
            _ev("failure", "Primary Grid Supply"),
            _ev("capacity_reduction", "Municipal Water Supply", {"reduction_pct": 50}),
            _ev("road_closure", "Central Avenue"),
        ],
    },
]