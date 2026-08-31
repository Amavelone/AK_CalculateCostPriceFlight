"""Зафиксированные migration-seed данные, однократно извлечённые из утверждённой legacy workbook."""

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


def baseline_manual_tariffs() -> list[dict[str, Any]]:
    return _records("manual_tariffs.json")


def migrate_legacy_workbook_data(state: dict[str, Any]) -> bool:
    """Однократно добавляет стабильные workbook-данные, не возвращая зависимость от workbook."""

    if state.get(_WORKBOOK_MIGRATION_MARKER):
        return False

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
    "migrate_legacy_workbook_data",
]
