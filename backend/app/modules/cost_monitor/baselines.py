"""Checked-in migration seeds derived once from the approved legacy workbook."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

_BASELINES_DIRECTORY = Path(__file__).with_name("baselines")
_WORKBOOK_MIGRATION_MARKER = "release_v1_workbook_ownership_migrated"


def _records(name: str) -> list[dict[str, Any]]:
    payload = json.loads((_BASELINES_DIRECTORY / name).read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or not isinstance(payload.get("records"), list):
        raise ValueError(f"Invalid Cost Monitor baseline: {name}")
    return copy.deepcopy(payload["records"])


def baseline_routes() -> list[dict[str, Any]]:
    return _records("routes.json")


def baseline_other_costs() -> dict[str, float]:
    return {str(item["airport"]): float(item["amount"]) for item in _records("airport_other_costs.json")}


def baseline_manual_tariffs() -> list[dict[str, Any]]:
    return _records("manual_tariffs.json")


def migrate_legacy_workbook_data(state: dict[str, Any]) -> bool:
    """Seed stable workbook-owned data once without restoring a workbook dependency."""

    if state.get(_WORKBOOK_MIGRATION_MARKER):
        return False

    if not state.get("routes"):
        state["routes"] = baseline_routes()
    if not state.get("other_costs"):
        state["other_costs"] = baseline_other_costs()

    manual_tariffs = []
    manual_keys: set[tuple[str, str]] = set()
    for item in state.get("manual_tariffs", []):
        manual = dict(item)
        manual.pop("legacy_manual", False)
        manual_tariffs.append(manual)
        manual_keys.add((str(manual.get("airport", "")), str(manual.get("service", ""))))
    for item in baseline_manual_tariffs():
        key = (str(item["airport"]), str(item["service"]))
        if key not in manual_keys:
            manual_tariffs.append(item)
            manual_keys.add(key)
    if manual_tariffs != state.get("manual_tariffs", []):
        state["manual_tariffs"] = manual_tariffs

    for key in ("international_airports", "aircraft_multipliers", "scenario_rates"):
        if key in state:
            state.pop(key)
    state[_WORKBOOK_MIGRATION_MARKER] = True
    return True


__all__ = [
    "baseline_manual_tariffs",
    "baseline_other_costs",
    "baseline_routes",
    "migrate_legacy_workbook_data",
]
