from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .parsers import (
    fetch_usd_rate,
    parse_fuel_registry,
    parse_monitor_workbook,
    parse_srv_tariffs,
)
from .records import CostMonitorDataset
from .source_adapters import SourceRunResult, adapter_for_parser
from .source_files import find_active_file, find_latest_file, save_uploaded_file, workbook_preview


@dataclass(frozen=True)
class SourceRefreshStage:
    """Нормализованный кандидат на activation; parser не меняет active state."""

    source_id: str
    file_name: str
    result: SourceRunResult
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
    adapter = adapter_for_parser(str(source["parser"]))
    if adapter.source_id != source_id:
        raise ValueError(f"Adapter {adapter.parser_id} не соответствует источнику {source_id}")
    result = adapter.load(path)
    return SourceRefreshStage(source_id, path.name, result, result.rows_read, result.preview, result.note, now)


def activate_staged_source(state: dict[str, Any], staged: SourceRefreshStage) -> dict[str, Any]:
    source = source_by_id(state, staged.source_id)
    if staged.result.source_id != staged.source_id:
        raise ValueError(f"Нельзя активировать результат {staged.result.source_id} для {staged.source_id}")

    # Physical parser result сначала применяет typed canonical dataset, и только
    # затем dataset сериализуется в local JSON adapter. Calculation не получает
    # raw workbook/JSON rows.
    dataset = CostMonitorDataset.from_state(state)
    staged.result.data.apply(dataset).write_to_state(state)

    source.update(
        {
            "last_status": "ready",
            "last_file": staged.file_name,
            "active_file": staged.file_name,
            "last_updated": staged.prepared_at,
            "last_error": None,
            "last_note": staged.note,
            "rows_read": staged.rows_read,
            "rows_loaded": staged.result.data.rows_loaded,
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
