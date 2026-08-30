from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .parsers import (
    fetch_usd_rate,
    parse_fuel_registry,
    parse_monitor_workbook,
    parse_srv_tariffs,
)
from .source_files import find_latest_file, save_uploaded_file, workbook_preview


PARSERS: dict[str, Callable[[Path], tuple[Any, int, list[dict[str, Any]], str | None]]] = {
    "srv_tariffs": parse_srv_tariffs,
    "fuel_registry": parse_fuel_registry,
    "monitor_workbook": parse_monitor_workbook,
}


def source_by_id(state: dict[str, Any], source_id: str) -> dict[str, Any]:
    for source in state["source_configs"]:
        if source["id"] == source_id:
            return source
    raise KeyError(source_id)


def refresh_source(state: dict[str, Any], source_id: str, now: str) -> dict[str, Any]:
    source = source_by_id(state, source_id)
    path = find_latest_file(source)
    parser = PARSERS[source["parser"]]
    result, rows_read, preview, note = parser(path)

    if source_id == "srv":
        state["imported_tariffs"] = result
        rows_loaded = len(result)
    elif source_id == "fuel_registry":
        state["fuel_prices"] = result
        rows_loaded = len(result)
    elif source_id == "monitor_workbook":
        state["routes"] = result["routes"]
        state["international_airports"] = result["international_airports"]
        state["other_costs"] = result["other_costs"]
        if result["aircraft_multipliers"]:
            state["aircraft_multipliers"] = result["aircraft_multipliers"]
        if result["scenario_rates"]:
            state["scenario_rates"] = result["scenario_rates"]
        non_legacy_manual = [item for item in state["manual_tariffs"] if not item.get("legacy_manual")]
        state["manual_tariffs"] = non_legacy_manual + result["legacy_manual_tariffs"]
        rows_loaded = len(result["routes"])
    else:
        rows_loaded = len(result)

    source.update(
        {
            "last_status": "ready",
            "last_file": path.name,
            "last_updated": now,
            "last_error": None,
            "last_note": note,
            "rows_read": rows_read,
            "rows_loaded": rows_loaded,
            "preview": preview,
        }
    )
    return source


def mark_source_error(state: dict[str, Any], source_id: str, message: str, now: str) -> dict[str, Any]:
    source = source_by_id(state, source_id)
    source.update({"last_status": "error", "last_error": message, "last_updated": now})
    return source


__all__ = [
    "fetch_usd_rate",
    "find_latest_file",
    "mark_source_error",
    "parse_fuel_registry",
    "parse_monitor_workbook",
    "parse_srv_tariffs",
    "refresh_source",
    "save_uploaded_file",
    "source_by_id",
    "workbook_preview",
]
