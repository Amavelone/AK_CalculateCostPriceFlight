from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .parsers import (
    fetch_usd_rate,
    parse_fuel_registry,
    parse_monitor_workbook,
    parse_srv_tariffs,
)
from .source_files import find_active_file, find_latest_file, save_uploaded_file, workbook_preview

PARSERS: dict[str, Callable[[Path], tuple[Any, int, list[dict[str, Any]], str | None]]] = {
    "srv_tariffs": parse_srv_tariffs,
    "fuel_registry": parse_fuel_registry,
    "monitor_workbook": parse_monitor_workbook,
}


@dataclass(frozen=True)
class SourceRefreshStage:
    """Нормализованный кандидат на activation; parser не меняет active state."""

    source_id: str
    file_name: str
    result: Any
    rows_read: int
    preview: list[dict[str, Any]]
    note: str | None
    prepared_at: str


def source_by_id(state: dict[str, Any], source_id: str) -> dict[str, Any]:
    for source in state["source_configs"]:
        if source["id"] == source_id:
            return source
    raise KeyError(source_id)


def stage_source_refresh(state: dict[str, Any], source_id: str, now: str) -> SourceRefreshStage:
    source = source_by_id(state, source_id)
    path = find_latest_file(source)
    parser = PARSERS[source["parser"]]
    result, rows_read, preview, note = parser(path)
    return SourceRefreshStage(source_id, path.name, result, rows_read, preview, note, now)


def activate_staged_source(state: dict[str, Any], staged: SourceRefreshStage) -> dict[str, Any]:
    source = source_by_id(state, staged.source_id)
    result = staged.result

    if staged.source_id == "srv":
        state["imported_tariffs"] = result
        rows_loaded = len(result)
    elif staged.source_id == "fuel_registry":
        state["fuel_prices"] = result
        rows_loaded = len(result)
    elif staged.source_id == "monitor_workbook":
        state["routes"] = result["routes"]
        state["international_airports"] = result["international_airports"]
        state["other_costs"] = result["other_costs"]
        # Пустой валидный раздел обязан заменить предыдущий набор, иначе новый
        # workbook маскируется старой sticky-конфигурацией.
        state["aircraft_multipliers"] = result["aircraft_multipliers"]
        state["scenario_rates"] = result["scenario_rates"]
        non_legacy_manual = [item for item in state["manual_tariffs"] if not item.get("legacy_manual")]
        state["manual_tariffs"] = non_legacy_manual + result["legacy_manual_tariffs"]
        rows_loaded = len(result["routes"])
    else:
        rows_loaded = len(result)

    source.update(
        {
            "last_status": "ready",
            "last_file": staged.file_name,
            "active_file": staged.file_name,
            "last_updated": staged.prepared_at,
            "last_error": None,
            "last_note": staged.note,
            "rows_read": staged.rows_read,
            "rows_loaded": rows_loaded,
            "preview": staged.preview,
        }
    )
    return source


def refresh_source(state: dict[str, Any], source_id: str, now: str) -> dict[str, Any]:
    return activate_staged_source(state, stage_source_refresh(state, source_id, now))


def mark_source_error(state: dict[str, Any], source_id: str, message: str, now: str) -> dict[str, Any]:
    source = source_by_id(state, source_id)
    source.update({"last_status": "error", "last_error": message, "last_updated": now})
    return source


__all__ = [
    "fetch_usd_rate",
    "find_active_file",
    "find_latest_file",
    "mark_source_error",
    "parse_fuel_registry",
    "parse_monitor_workbook",
    "parse_srv_tariffs",
    "refresh_source",
    "stage_source_refresh",
    "activate_staged_source",
    "save_uploaded_file",
    "source_by_id",
    "workbook_preview",
]
