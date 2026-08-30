from __future__ import annotations

import copy
import json
import os
import tempfile
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ...core.config import Settings


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _default_scenarios() -> dict[str, dict[str, list[float]]]:
    # Настраиваемые начальные значения действуют до чтения книги конфигурации.
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
    """Создаёт минимальное начальное состояние до первого обновления источников.

    Значения сценариев и множителей соответствуют текущей рабочей базе, а
    фактические тарифы, маршруты и цены поступают только из внешних файлов.
    """

    shared_path = str(source_dir)
    return {
        "version": 1,
        "created_at": utc_now(),
        # Монотонный номер активного набора расчётных данных. Он не заменяет
        # снимки истории, но делает версию исходных данных видимой клиентам API.
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
                "active_file": None,
                "uploaded_file": None,
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
                "active_file": None,
                "uploaded_file": None,
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
                "active_file": None,
                "uploaded_file": None,
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
    """Предоставляет потокобезопасное атомарное локальное хранилище JSON.

    Узкий интерфейс чтения и изменения служит границей для будущего репозитория
    PostgreSQL: API и расчётный модуль не работают с файлом напрямую.
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
        """Добавляет совместимые значения по умолчанию в ранее созданное хранилище."""

        with self._lock:
            state = self._read()
            changed = False
            if "data_revision" not in state:
                has_calculation_data = any(
                    state.get(key) for key in ("imported_tariffs", "manual_tariffs", "fuel_prices", "routes")
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
            source_configs = state.get("source_configs", [])
            active_source_configs = [
                source
                for source in source_configs
                if source.get("parser") in {"srv_tariffs", "fuel_registry", "monitor_workbook"}
            ]
            if len(active_source_configs) != len(source_configs):
                state["source_configs"] = active_source_configs
                changed = True
            for source in state.get("source_configs", []):
                if "active_file" not in source:
                    source["active_file"] = source.get("last_file") if source.get("last_status") == "ready" else None
                    changed = True
                if "uploaded_file" not in source:
                    source["uploaded_file"] = None
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
        """Повышает ревизию активных данных после успешного изменения источников."""

        revision = int(state.get("data_revision", 0)) + 1
        state["data_revision"] = revision
        state["data_updated_at"] = utc_now()
        return revision
