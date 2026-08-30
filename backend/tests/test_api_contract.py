from __future__ import annotations

import copy
import unittest
from pathlib import Path
from unittest.mock import patch

from app import main
from app.modules.cost_monitor.store import build_default_state, utc_now
from app.modules.cost_monitor import api as cost_api
from app.modules.cost_monitor.sources import source_by_id


EXPECTED_OPERATIONS = {
    ("GET", "/api/health"),
    ("GET", "/api/dashboard"),
    ("GET", "/api/calculation-options"),
    ("GET", "/api/drafts/current"),
    ("PUT", "/api/drafts/current"),
    ("POST", "/api/calculations"),
    ("POST", "/api/exports/{file_format}"),
    ("GET", "/api/sources"),
    ("PUT", "/api/sources/{source_id}"),
    ("GET", "/api/sources/{source_id}/preview"),
    ("GET", "/api/sources/{source_id}/raw-preview"),
    ("POST", "/api/sources/{source_id}/refresh"),
    ("POST", "/api/sources/refresh-all"),
    ("POST", "/api/sources/{source_id}/upload"),
    ("GET", "/api/tariffs"),
    ("POST", "/api/tariffs/manual"),
    ("DELETE", "/api/tariffs/manual/{tariff_id}"),
    ("GET", "/api/routes"),
    ("GET", "/api/audit"),
}


class MemoryStore:
    """Минимальный тестовый двойник, фиксирующий текущий контракт хранилища."""

    def __init__(self, state: dict) -> None:
        self.state = copy.deepcopy(state)

    def mutate(self, operation):
        return copy.deepcopy(operation(self.state))

    def append_audit(self, state: dict, action: str, detail: str) -> None:
        state.setdefault("audit_log", []).append({"at": utc_now(), "action": action, "detail": detail})

    def mark_calculation_data_changed(self, state: dict) -> int:
        revision = int(state.get("data_revision", 0)) + 1
        state["data_revision"] = revision
        state["data_updated_at"] = utc_now()
        return revision


class ApiContractTests(unittest.TestCase):
    def test_current_api_operations_are_stable(self) -> None:
        specification = main.app.openapi()
        actual = {
            (method.upper(), path)
            for path, operations in specification["paths"].items()
            for method in operations
        }
        self.assertEqual(actual, EXPECTED_OPERATIONS)

    def test_refresh_all_currently_publishes_partial_success(self) -> None:
        state = build_default_state(Path("sources"))
        state["data_revision"] = 4
        state["imported_tariffs"] = [{"airport": "OLD", "service": "ВОДА", "rate": 1}]
        state["fuel_prices"] = [{"airport": "OLD", "price": 1}]
        state["routes"] = [{"key": "OLD-OLD", "flight_time": 1, "distance": 1}]
        memory_store = MemoryStore(state)

        def refresh_with_one_failure(active_state: dict, source_id: str, now: str) -> dict:
            if source_id == "fuel_registry":
                raise ValueError("invalid fuel workbook")
            source = source_by_id(active_state, source_id)
            source.update({"last_status": "ready", "last_updated": now, "last_error": None})
            if source_id == "srv":
                active_state["imported_tariffs"] = [{"airport": "NEW", "service": "ВОДА", "rate": 2}]
            if source_id == "monitor_workbook":
                active_state["routes"] = [{"key": "NEW-NEW", "flight_time": 2, "distance": 2}]
            return source

        with (
            patch.object(cost_api, "store", memory_store),
            patch.object(cost_api, "refresh_source", side_effect=refresh_with_one_failure),
        ):
            response = cost_api.refresh_all_sources()

        failed = next(source for source in response["sources"] if source["id"] == "fuel_registry")
        self.assertEqual(failed["last_status"], "error")
        self.assertEqual(memory_store.state["data_revision"], 5)
        self.assertEqual(memory_store.state["imported_tariffs"][0]["airport"], "NEW")
        self.assertEqual(memory_store.state["routes"][0]["key"], "NEW-NEW")
        self.assertEqual(memory_store.state["fuel_prices"][0]["airport"], "OLD")


if __name__ == "__main__":
    unittest.main()
