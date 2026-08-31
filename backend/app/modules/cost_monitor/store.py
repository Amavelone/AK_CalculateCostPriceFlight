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
from .baselines import baseline_manual_tariffs, migrate_legacy_workbook_data
from .configuration.definition import (
    PRODUCTION_SOURCE_DEFINITIONS,
    SourceDefinition,
)
from .configuration.service import ensure_configuration_state, ensure_release_configuration_ownership
from .reference_data.service import ensure_reference_data_state


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def default_source_config(binding: SourceDefinition, source_dir: Path) -> dict[str, Any]:
    return {
        "id": binding.id,
        "label": binding.label,
        "description": binding.description,
        "directory": str(source_dir),
        "mask": binding.default_mask,
        "parser": binding.parser,
        "last_status": "not_updated",
        "last_file": None,
        "active_file": None,
        "uploaded_file": None,
        "last_updated": None,
        "last_error": None,
        "rows_read": 0,
        "rows_loaded": 0,
        "preview": [],
    }


def build_default_state(source_dir: Path) -> dict[str, Any]:
    """Creates production state seeded with stable, checked-in module data."""

    state = {
        "version": 1,
        "created_at": utc_now(),
        # Монотонный номер активного набора расчётных данных. Он не заменяет
        # снимки истории, но делает версию исходных данных видимой клиентам API.
        "data_revision": 0,
        "data_updated_at": None,
        "source_configs": [default_source_config(binding, source_dir) for binding in PRODUCTION_SOURCE_DEFINITIONS],
        "imported_tariffs": [],
        "manual_tariffs": baseline_manual_tariffs(),
        "fuel_prices": [],
        "release_v1_workbook_ownership_migrated": True,
        "drafts": {},
        "audit_log": [],
    }
    ensure_configuration_state(state, state["created_at"])
    ensure_release_configuration_ownership(state)
    ensure_reference_data_state(state, state["created_at"])
    return state


class JsonStore:
    """Предоставляет потокобезопасное атомарное локальное хранилище JSON.

    Узкий module repository contract отделяет local JSON adapter от API и
    calculation dataset; SQL Server implementation остаётся будущим этапом.
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
            existing_sources = {
                source.get("id"): source
                for source in source_configs
                if any(
                    source.get("id") == definition.id and source.get("parser") == definition.parser
                    for definition in PRODUCTION_SOURCE_DEFINITIONS
                )
            }
            active_source_configs = []
            for definition in PRODUCTION_SOURCE_DEFINITIONS:
                source = default_source_config(definition, self._source_dir)
                source.update(existing_sources.get(definition.id, {}))
                source.update(
                    {
                        "id": definition.id,
                        "label": definition.label,
                        "description": definition.description,
                        "parser": definition.parser,
                    }
                )
                active_source_configs.append(source)
            if active_source_configs != source_configs:
                state["source_configs"] = active_source_configs
                changed = True
            for source in state.get("source_configs", []):
                if "active_file" not in source:
                    source["active_file"] = source.get("last_file") if source.get("last_status") == "ready" else None
                    changed = True
                if "uploaded_file" not in source:
                    source["uploaded_file"] = None
                    changed = True
            if ensure_configuration_state(state):
                changed = True
            if ensure_release_configuration_ownership(state):
                changed = True
            if migrate_legacy_workbook_data(state):
                self.append_audit(state, "legacy_workbook_ownership_migrated", "stable baseline data seeded")
                changed = True
            if ensure_reference_data_state(state):
                self.append_audit(state, "reference_data_v1_migrated", "routes and airport other costs versioned")
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
