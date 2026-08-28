from __future__ import annotations

import copy
import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .config import Settings


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_scenarios() -> dict[str, dict[str, list[float]]]:
    # Initial, configurable values used until the configuration workbook is parsed.
    return {
        "ГБ 2026": {
            "733": [78.48, 220.45, 272.17],
            "737": [120.0, 280.0, 340.0],
            "738": [165.73, 341.48, 391.28],
        },
        "Оперативная 2026": {
            "733": [78.48, 220.45, 272.17],
            "737": [120.0, 280.0, 340.0],
            "738": [165.73, 341.48, 391.28],
        },
    }


def build_default_state(source_dir: Path) -> dict[str, Any]:
    """A small, self-explaining initial state; actual data arrives through refresh."""

    shared_path = str(source_dir)
    return {
        "version": 1,
        "created_at": utc_now(),
        # Monotonically increasing marker of the active calculation data. It is
        # not a replacement for historical snapshots, but makes the input state
        # of a result visible to the user and API clients.
        "data_revision": 0,
        "data_updated_at": None,
        "source_configs": [
            {
                "id": "srv",
                "label": "Тарифы SRV",
                "description": "Тарифы услуг аэропортов",
                "directory": shared_path,
                "mask": "7480_srv*.xlsx",
                "parser": "srv_tariffs",
                "last_status": "not_updated",
                "last_file": None,
                "last_updated": None,
                "last_error": None,
                "rows_read": 0,
                "rows_loaded": 0,
                "preview": [],
            },
            {
                "id": "nad",
                "label": "Надбавки и скидки NAD",
                "description": "Файл NAD; текущая Excel-логика отбрасывает его строки без ставки",
                "directory": shared_path,
                "mask": "7480_nad*.xlsx",
                "parser": "nad_baseline",
                "last_status": "not_updated",
                "last_file": None,
                "last_updated": None,
                "last_error": None,
                "rows_read": 0,
                "rows_loaded": 0,
                "preview": [],
            },
            {
                "id": "fuel_registry",
                "label": "Реестр керосина",
                "description": "Выгрузка 1С цен поставщиков",
                "directory": shared_path,
                "mask": "реестр*.xlsx",
                "parser": "fuel_registry",
                "last_status": "not_updated",
                "last_file": None,
                "last_updated": None,
                "last_error": None,
                "rows_read": 0,
                "rows_loaded": 0,
                "preview": [],
            },
            {
                "id": "monitor_workbook",
                "label": "Рабочая книга монитора",
                "description": "Маршруты, признак МВЛ и исходные параметры",
                "directory": shared_path,
                "mask": "Расчет себестоимости рейсов*.xlsx",
                "parser": "monitor_workbook",
                "last_status": "not_updated",
                "last_file": None,
                "last_updated": None,
                "last_error": None,
                "rows_read": 0,
                "rows_loaded": 0,
                "preview": [],
            },
        ],
        "imported_tariffs": [],
        "manual_tariffs": [],
        "fuel_prices": [],
        "routes": [],
        "international_airports": {},
        "other_costs": {},
        "scenario_rates": _default_scenarios(),
        "aircraft_multipliers": {"733": 1.0, "737": 1.0, "738": 1.0},
        "drafts": {},
        "audit_log": [],
    }


class JsonStore:
    """Thread-safe, atomic local development storage.

    Its narrow read/mutate interface is intentionally the seam for a future
    PostgreSQL repository. No API or calculation service talks to a file directly.
    """

    def __init__(self, settings: Settings) -> None:
        self._path = settings.data_dir / "store.json"
        self._source_dir = settings.default_source_dir
        self._lock = threading.RLock()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._write(build_default_state(self._source_dir))
        else:
            self._migrate_state()

    def _migrate_state(self) -> None:
        """Apply small backwards-compatible schema defaults to local stores."""

        with self._lock:
            state = self._read()
            changed = False
            if "data_revision" not in state:
                has_calculation_data = any(
                    state.get(key)
                    for key in ("imported_tariffs", "manual_tariffs", "fuel_prices", "routes")
                )
                state["data_revision"] = 1 if has_calculation_data else 0
                changed = True
            if "data_updated_at" not in state:
                timestamps = [
                    source.get("last_updated")
                    for source in state.get("source_configs", [])
                    if source.get("last_updated")
                ]
                state["data_updated_at"] = max(timestamps) if timestamps else None
                changed = True
            if changed:
                self._write(state)

    def _read(self) -> dict[str, Any]:
        with self._path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _write(self, state: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        handle, temp_path = tempfile.mkstemp(prefix="store-", suffix=".json", dir=self._path.parent)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as file:
                json.dump(state, file, ensure_ascii=False, indent=2)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp_path, self._path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def read(self) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._read())

    def mutate(self, operation: Callable[[dict[str, Any]], Any]) -> Any:
        with self._lock:
            state = self._read()
            result = operation(state)
            self._write(state)
            return copy.deepcopy(result)

    def append_audit(self, state: dict[str, Any], action: str, detail: str) -> None:
        events = state.setdefault("audit_log", [])
        events.append({"at": utc_now(), "action": action, "detail": detail})
        del events[:-100]

    def mark_calculation_data_changed(self, state: dict[str, Any]) -> int:
        """Advance the active data revision after a successful data mutation."""

        revision = int(state.get("data_revision", 0)) + 1
        state["data_revision"] = revision
        state["data_updated_at"] = utc_now()
        return revision
