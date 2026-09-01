from __future__ import annotations

import copy
import unittest
from pathlib import Path
from unittest.mock import patch

from app.modules.cost_monitor import api as cost_api
from app.modules.cost_monitor.configuration import (
    ConfigurationNotFoundError,
    ConfigurationService,
    ConfigurationValidationError,
    JsonConfigurationRepository,
)
from app.modules.cost_monitor.reference_data import ReferenceDataService
from app.modules.cost_monitor.reference_data.repository import JsonReferenceDataRepository
from app.modules.cost_monitor.schemas import CalculationRequest
from app.modules.cost_monitor.store import build_default_state, utc_now
from fastapi import HTTPException


class MemoryConfigurationStore:
    """Тестовый JSON adapter с тем же узким контрактом, что JsonStore."""

    def __init__(self, state: dict) -> None:
        self.state = copy.deepcopy(state)

    def read(self) -> dict:
        return copy.deepcopy(self.state)

    def mutate(self, operation):
        return copy.deepcopy(operation(self.state))

    def append_audit(self, state: dict, action: str, detail: str) -> None:
        state.setdefault("audit_log", []).append({"at": utc_now(), "action": action, "detail": detail})


class ConfigurationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = MemoryConfigurationStore(build_default_state(Path("sources")))
        self.service = ConfigurationService(JsonConfigurationRepository(self.store))

    def draft_with_custom_fuel_rate(self, rate: float = 3.0) -> int:
        draft = self.service.create_draft()
        candidate = draft["configuration"]
        candidate["fuel"]["consumption_tons_per_hour"] = rate
        self.service.update_draft(draft["version"], candidate)
        return draft["version"]

    def request(self) -> CalculationRequest:
        return CalculationRequest.model_validate(
            {
                "legs": [{"id": "one", "departure": "AAA", "arrival": "BBB", "aircraft": "738", "passengers": 0}],
                "settings": {"scenario": "ГБ 2026", "fuel_source": "ЦРТ", "catering": False},
            }
        )

    def calculation_state(self) -> dict:
        state = self.store.read()
        state.update(
            {
                "imported_tariffs": [
                    {"airport": "AAA", "service": "КЕРОСИН", "rate": 100},
                    {"airport": "AAA", "service": "ЗАПРАВКА ВС", "rate": 20},
                    {"airport": "AAA", "service": "АНО АД", "rate": 1000},
                ],
            }
        )
        state["reference_data_versions"][0]["reference_data"] = {
            "schema_version": "1.0",
            "routes": [{"departure": "AAA", "arrival": "BBB", "flight_time": 2, "distance": 100}],
            "airport_other_costs": [],
        }
        return state

    def test_draft_isolated_validated_compared_and_activated(self) -> None:
        self.assertEqual(self.service.active()["version"], 1)
        self.assertEqual(self.service.active()["configuration"].fuel.consumption_tons_per_hour, 2.7)

        draft_version = self.draft_with_custom_fuel_rate()
        self.assertEqual(self.service.active()["configuration"].fuel.consumption_tons_per_hour, 2.7)
        self.assertEqual(self.service.validate_draft(draft_version)["validation_status"], "valid")

        comparison = self.service.compare(1, draft_version)
        self.assertEqual(comparison["changes"][0]["path"], "fuel.consumption_tons_per_hour")
        self.assertEqual(comparison["changes"][0]["kind"], "parameter_changed")

        activated = self.service.activate(draft_version)
        self.assertEqual(activated["state"], "active")
        self.assertEqual(self.service.active()["version"], draft_version)
        self.assertEqual([item["state"] for item in self.service.list_versions()], ["inactive", "active"])
        self.assertEqual(self.store.state["configuration_drafts"], {})

    def test_default_is_explicit_immutable_baseline_and_draft_can_start_from_it(self) -> None:
        default = self.service.default()
        self.assertTrue(default["is_default"])
        self.assertEqual(default["version"], 1)
        original = default["configuration"].model_dump(mode="json")

        from_default = self.service.create_draft("default")
        self.assertEqual(from_default["base_version"], 1)
        from_default["configuration"]["fuel"]["consumption_tons_per_hour"] = 3.0
        self.service.update_draft(from_default["version"], from_default["configuration"])
        self.service.activate(from_default["version"])

        self.assertEqual(self.service.active()["version"], from_default["version"])
        self.assertEqual(self.service.default()["configuration"].model_dump(mode="json"), original)
        self.assertTrue(self.service.default()["is_default"])
        from_active = self.service.create_draft("active")
        self.assertEqual(from_active["base_version"], from_default["version"])
        self.service.rollback(1)
        self.assertEqual(self.service.active()["version"], 1)
        self.assertEqual(self.service.default()["configuration"].model_dump(mode="json"), original)

    def test_business_facade_updates_only_registered_values_and_keeps_operations(self) -> None:
        draft = self.service.create_draft("default")
        before_operations = copy.deepcopy(draft["configuration"]["operations"])
        business = self.service.business_draft(draft["version"])["business"]
        self.assertEqual(business["metadata"]["parameters"][0]["id"], "vat.rate")
        self.assertIn("where_used", business["metadata"]["parameters"][0])
        self.assertEqual(business["values"]["fuel.consumption_tons_per_hour"], 2.7)

        updated = self.service.update_business_draft(
            draft["version"],
            {"values": {"fuel.consumption_tons_per_hour": 3.0, "ground.split_divisor": 3}},
        )
        self.assertEqual(updated["configuration"]["fuel"]["consumption_tons_per_hour"], 3.0)
        self.assertEqual(updated["configuration"]["ground"]["split_divisor"], 3)
        self.assertEqual(updated["configuration"]["operations"], before_operations)
        with self.assertRaises(ConfigurationValidationError):
            self.service.update_business_draft(draft["version"], {"values": {"operations.ano": {}}})
        with self.assertRaises(ConfigurationValidationError):
            self.service.update_business_draft(
                draft["version"],
                {"flight_hour": {"aircraft_multipliers": {"NEW": 1}}},
            )

    def test_draft_delete_export_and_grouped_compare_are_safe(self) -> None:
        draft = self.service.create_draft("default")
        changed = self.service.update_business_draft(
            draft["version"], {"values": {"fuel.consumption_tons_per_hour": 3.0}}
        )
        comparison = self.service.compare(1, changed["version"])
        self.assertEqual(comparison["changes"][0]["presentation"]["label"], "Расход топлива")
        self.assertEqual(comparison["changes"][0]["presentation"]["group"], "fuel")
        snapshot = self.service.export_snapshot(draft["version"])
        self.assertEqual(snapshot["export_schema_version"], "1.0")
        self.assertEqual(snapshot["configuration_identity"]["state"], "draft")
        self.assertNotIn("secrets", snapshot)
        self.service.delete_draft(draft["version"])
        with self.assertRaises(ConfigurationNotFoundError):
            self.service.draft(draft["version"])
        with self.assertRaises(ConfigurationNotFoundError):
            self.service.delete_draft(1)

    def test_active_version_cannot_be_edited_and_invalid_candidate_is_rejected(self) -> None:
        with self.assertRaises(ConfigurationNotFoundError):
            self.service.update_draft(1, self.service.active()["configuration"].model_dump(mode="json"))

        draft = self.service.create_draft()
        invalid = draft["configuration"]
        invalid["fuel"]["consumption_tons_per_hour"] = 0
        with self.assertRaises(ConfigurationValidationError):
            self.service.update_draft(draft["version"], invalid)
        self.assertEqual(self.service.draft_configuration(draft["version"]).fuel.consumption_tons_per_hour, 2.7)

    def test_preview_does_not_activate_and_rollback_reuses_immutable_version(self) -> None:
        memory_store = MemoryConfigurationStore(self.calculation_state())
        service = ConfigurationService(JsonConfigurationRepository(memory_store))
        reference_service = ReferenceDataService(JsonReferenceDataRepository(memory_store))
        # Новый service начинается с v1; draft создаётся на том же state, что использует API preview.
        draft_version = service.create_draft()["version"]
        candidate = service.draft_configuration(draft_version).model_dump(mode="json")
        candidate["fuel"]["consumption_tons_per_hour"] = 3.0
        service.update_draft(draft_version, candidate)

        with (
            patch.object(cost_api, "repository", memory_store),
            patch.object(cost_api, "configuration_service", service),
            patch.object(cost_api, "reference_data_service", reference_service),
        ):
            preview = cost_api.preview_configuration_draft(draft_version, self.request())
            self.assertEqual(preview["configuration_state"], "draft")
            self.assertEqual(preview["config_version"], draft_version)
            self.assertEqual(preview["legs"][0]["components"]["fuel"], 720.0)
            self.assertEqual(service.active()["version"], 1)

            cost_api.activate_configuration_draft(draft_version)
            active = cost_api.calculate_cost(self.request())
            self.assertEqual(active["configuration_state"], "active")
            self.assertEqual(active["config_version"], draft_version)
            self.assertEqual(active["legs"][0]["components"]["fuel"], 720.0)

            restored = cost_api.rollback_configuration(1)
            self.assertEqual(restored["version"], 1)
            self.assertEqual(service.active()["configuration"].fuel.consumption_tons_per_hour, 2.7)
            self.assertIn("configuration_rolled_back", [event["action"] for event in memory_store.state["audit_log"]])

    def test_ano_parameter_and_catering_composition_preview_activate_and_rollback(self) -> None:
        memory_store = MemoryConfigurationStore(self.calculation_state())
        service = ConfigurationService(JsonConfigurationRepository(memory_store))
        reference_service = ReferenceDataService(JsonReferenceDataRepository(memory_store))
        draft = service.create_draft()
        candidate = draft["configuration"]
        candidate["overrides"]["aircraft_multipliers"] = {"738": 1}
        candidate["overrides"]["scenario_rates"] = {"ГБ 2026": {"738": [10, 20, 30]}}
        candidate["ano"]["route_rate_per_100_km"] = 1742.3
        passenger_condition = copy.deepcopy(candidate["operations"]["catering"]["parts"][1]["condition"])
        candidate["operations"]["catering"]["parts"].append(
            {
                "id": "extra_passenger_component",
                "label": "Дополнительная пассажирская часть",
                "detail_service": "ДОПОЛНИТЕЛЬНАЯ ЧАСТЬ",
                "initial": {"kind": "variable", "name": "passengers"},
                "operations": [
                    {
                        "operation": "multiply",
                        "operand": {"kind": "constant", "value": 200},
                        "digits": None,
                    }
                ],
                "condition": passenger_condition,
            }
        )
        service.update_draft(draft["version"], candidate)
        semantic_changes = service.compare(1, draft["version"])["changes"]
        self.assertIn("operation_added", {change["kind"] for change in semantic_changes})
        self.assertIn("parameter_changed", {change["kind"] for change in semantic_changes})
        request = CalculationRequest.model_validate(
            {
                "legs": [{"id": "one", "departure": "AAA", "arrival": "BBB", "aircraft": "738", "passengers": 10}],
                "settings": {"scenario": "ГБ 2026", "fuel_source": "ЦРТ", "catering": True},
            }
        )

        with (
            patch.object(cost_api, "repository", memory_store),
            patch.object(cost_api, "configuration_service", service),
            patch.object(cost_api, "reference_data_service", reference_service),
        ):
            comparison = cost_api.preview_configuration_comparison(draft["version"], request)
            self.assertEqual(comparison["active"]["legs"][0]["components"]["catering"], 14000)
            self.assertEqual(comparison["draft"]["legs"][0]["components"]["catering"], 16000)
            self.assertEqual(comparison["draft"]["legs"][0]["components"]["ano"], 2742.3)
            catering_trace = next(
                step
                for step in comparison["draft"]["trace"]["legs"][0]["steps"]
                if step["component"] == "catering" and step["stage"] == "operation"
            )
            self.assertIn("extra_passenger_component", {part["id"] for part in catering_trace["values"]["parts"]})
            self.assertEqual(service.active()["version"], 1)

            service.activate(draft["version"])
            active_result = cost_api.calculate_cost(request)
            self.assertEqual(active_result["legs"][0]["components"]["catering"], 16000)
            service.rollback(1)
            restored = cost_api.calculate_cost(request)
            self.assertEqual(restored["legs"][0]["components"]["catering"], 14000)

    def test_configuration_rates_are_effective_and_trace_configuration_owner(self) -> None:
        memory_store = MemoryConfigurationStore(self.calculation_state())
        service = ConfigurationService(JsonConfigurationRepository(memory_store))
        reference_service = ReferenceDataService(JsonReferenceDataRepository(memory_store))
        draft = service.create_draft()
        candidate = draft["configuration"]
        candidate["overrides"]["aircraft_multipliers"]["738"] = 1.5
        candidate["overrides"]["scenario_rates"]["ГБ 2026"] = {"738": [11, 21, 31]}
        service.update_draft(draft["version"], candidate)

        with (
            patch.object(cost_api, "repository", memory_store),
            patch.object(cost_api, "configuration_service", service),
            patch.object(cost_api, "reference_data_service", reference_service),
        ):
            preview = cost_api.preview_configuration_draft(draft["version"], self.request())

        ground_parameters = next(
            step
            for step in preview["trace"]["legs"][0]["steps"]
            if step["component"] == "ground" and step["stage"] == "parameters"
        )
        self.assertEqual(ground_parameters["values"]["aircraft_multiplier"]["origin"], "runtime_configuration")
        self.assertEqual(ground_parameters["values"]["aircraft_multiplier"]["reference"], "738")
        margin = next(
            step
            for step in preview["trace"]["legs"][0]["steps"]
            if step["component"] == "margin" and step["stage"] == "operation"
        )
        self.assertTrue(all(rate["origin"] == "runtime_configuration" for rate in margin["values"]["rates"]))

    def test_api_maps_missing_and_invalid_lifecycle_transitions_to_client_errors(self) -> None:
        with (
            patch.object(cost_api, "repository", self.store),
            patch.object(cost_api, "configuration_service", self.service),
        ):
            with self.assertRaises(HTTPException) as missing:
                cost_api.activate_configuration_draft(99)
            self.assertEqual(missing.exception.status_code, 404)

            with self.assertRaises(HTTPException) as conflict:
                cost_api.rollback_configuration(1)
            self.assertEqual(conflict.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
