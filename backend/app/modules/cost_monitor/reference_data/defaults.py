import json
from pathlib import Path
from typing import Any

from .schema import CostMonitorReferenceData

_DEFAULTS_DIRECTORY = Path(__file__).with_name("defaults")


def _read_records(name: str) -> list[dict[str, Any]]:
    payload = json.loads((_DEFAULTS_DIRECTORY / name).read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or not isinstance(payload.get("records"), list):
        raise ValueError(f"Invalid Cost Monitor Reference Data baseline: {name}")
    return payload["records"]


def load_baseline_reference_data() -> CostMonitorReferenceData:
    routes = [
        {
            "departure": item["departure"],
            "arrival": item["arrival"],
            "distance": item["distance"],
            "flight_time": item["flight_time"],
            "source_row": item.get("source_row"),
        }
        for item in _read_records("routes.json")
    ]
    other_costs = [
        {"airport": item["airport"], "amount": item["amount"]}
        for item in _read_records("airport_other_costs.json")
    ]
    return CostMonitorReferenceData(routes=routes, airport_other_costs=other_costs)


BASELINE_REFERENCE_DATA = load_baseline_reference_data()


__all__ = ["BASELINE_REFERENCE_DATA", "load_baseline_reference_data"]
