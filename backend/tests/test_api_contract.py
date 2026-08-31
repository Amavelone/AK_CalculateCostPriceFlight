from __future__ import annotations

import copy
import unittest
from pathlib import Path
from unittest.mock import patch

from app import main
from app.modules.cost_monitor import api as cost_api
from app.modules.cost_monitor.source_adapters import SourceRunResult, SrvTariffData
from app.modules.cost_monitor.sources import SourceRefreshStage
from app.modules.cost_monitor.store import build_default_state, utc_now

EXPECTED_OPERATIONS = {
    ("GET", "/api/health"),
    ("GET", "/api/dashboard"),
    ("GET", "/api/calculation-options"),
    ("GET", "/api/drafts/current"),
    ("PUT", "/api/drafts/current"),
    ("POST", "/api/calculations"),
    ("POST", "/api/exports/{file_format}"),
    ("GET", "/api/configuration/active"),
    ("GET", "/api/configuration/versions"),
    ("GET", "/api/configuration/capabilities"),
    ("POST", "/api/configuration/drafts"),
    ("GET", "/api/configuration/drafts/{version}"),
    ("PUT", "/api/configuration/drafts/{version}"),
    ("POST", "/api/configuration/drafts/{version}/validate"),
    ("GET", "/api/configuration/compare/{left_version}/{right_version}"),
    ("POST", "/api/configuration/drafts/{version}/preview"),
    ("POST", "/api/configuration/drafts/{version}/preview-comparison"),
    ("POST", "/api/configuration/drafts/{version}/activate"),
    ("POST", "/api/configuration/rollback/{version}"),
    ("GET", "/api/reference-data/active"),
    ("GET", "/api/reference-data/versions"),
    ("POST", "/api/reference-data/drafts"),
    ("GET", "/api/reference-data/drafts/{version}"),
    ("PUT", "/api/reference-data/drafts/{version}"),
    ("POST", "/api/reference-data/drafts/{version}/validate"),
    ("GET", "/api/reference-data/compare/{left_version}/{right_version}"),
    ("POST", "/api/reference-data/drafts/{version}/preview"),
    ("POST", "/api/reference-data/drafts/{version}/preview-comparison"),
    ("POST", "/api/reference-data/drafts/{version}/activate"),
    ("POST", "/api/reference-data/rollback/{version}"),
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

    def test_calculation_response_has_explicit_openapi_contract(self) -> None:
        operation = main.app.openapi()["paths"]["/api/calculations"]["post"]
        schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
        self.assertEqual(schema, {"$ref": "#/components/schemas/CalculationResponse"})

    def test_admin_route_is_separate_from_api_and_root_spa(self) -> None:
        admin_routes = [route for route in main.app.routes if getattr(route, "path", None) == "/admin"]
        self.assertEqual(len(admin_routes), 1)
        self.assertNotIn("/admin", main.app.openapi()["paths"])
        if main.frontend_dist.exists():
            self.assertTrue(any(getattr(route, "name", None) == "frontend" for route in main.app.routes))

    def test_refresh_all_preserves_active_dataset_when_any_source_fails(self) -> None:
        state = build_default_state(Path("sources"))
        state["data_revision"] = 4
        state["imported_tariffs"] = [{"airport": "OLD", "service": "ВОДА", "rate": 1}]
        state["fuel_prices"] = [{"airport": "OLD", "price": 1}]
        state["reference_data_versions"][0]["reference_data"]["routes"] = [
            {"departure": "OLD", "arrival": "OLD", "flight_time": 1, "distance": 1, "source_row": None}
        ]
        memory_store = MemoryStore(state)
        staged_source_ids: list[str] = []

        def stage_with_one_failure(active_state: dict, source_id: str, now: str) -> SourceRefreshStage:
            staged_source_ids.append(source_id)
            if source_id == "fuel_registry":
                raise ValueError("invalid fuel workbook")
            return SourceRefreshStage(
                source_id,
                f"{source_id}.xlsx",
                SourceRunResult(source_id, SrvTariffData(()), 1, [], None),
                1,
                [],
                None,
                now,
            )

        with (
            patch.object(cost_api, "repository", memory_store),
            patch.object(cost_api, "stage_source_refresh", side_effect=stage_with_one_failure),
        ):
            response = cost_api.refresh_all_sources()

        failed = next(source for source in response["sources"] if source["id"] == "fuel_registry")
        self.assertEqual(failed["last_status"], "error")
        self.assertEqual(memory_store.state["data_revision"], 4)
        self.assertEqual(memory_store.state["imported_tariffs"][0]["airport"], "OLD")
        self.assertEqual(
            memory_store.state["reference_data_versions"][0]["reference_data"]["routes"][0]["departure"],
            "OLD",
        )
        self.assertEqual(memory_store.state["fuel_prices"][0]["airport"], "OLD")
        self.assertEqual(staged_source_ids, ["srv", "fuel_registry"])
        self.assertEqual([source["id"] for source in response["sources"]], ["srv", "fuel_registry"])


if __name__ == "__main__":
    unittest.main()
