from __future__ import annotations

import unittest
from pathlib import Path

from app.modules.cost_monitor.calculation import calculate
from app.modules.cost_monitor.configuration import BASELINE_CONFIGURATION, validate_configuration
from app.modules.cost_monitor.configuration.definition import (
    COMPATIBILITY_SOURCE_DEFINITIONS,
    PRODUCTION_SOURCE_DEFINITIONS,
)
from app.modules.cost_monitor.configuration.functions import ALLOWED_PRIMITIVE_NAMES
from app.modules.cost_monitor.configuration.variables import REGISTERED_VARIABLE_NAMES
from app.modules.cost_monitor.records import CostMonitorDataset
from app.modules.cost_monitor.schemas import CalculationRequest
from app.modules.cost_monitor.store import build_default_state
from pydantic import ValidationError


class ConfigurationTests(unittest.TestCase):
    def test_baseline_contains_excel_owned_parameters(self) -> None:
        configuration = BASELINE_CONFIGURATION

        self.assertEqual(configuration.schema_version, "2.0")
        self.assertEqual(configuration.fuel.consumption_tons_per_hour, 2.7)
        self.assertEqual(configuration.ano.route_rate_per_100_km, 1666.6)
        self.assertEqual(
            configuration.catering.model_dump(),
            {"base_units": 6, "base_unit_rate": 1500.0, "passenger_surcharge": 500.0},
        )
        self.assertEqual(configuration.vat.airports, ("DME", "SVO", "VKO"))
        self.assertEqual(configuration.ground.fire_truck_rate, 25132)
        self.assertEqual(
            {binding.id: binding.default_mask for binding in PRODUCTION_SOURCE_DEFINITIONS},
            {
                "srv": "7480_srv*.xlsx",
                "fuel_registry": "реестр*.xlsx",
            },
        )
        self.assertEqual(
            [binding.id for binding in COMPATIBILITY_SOURCE_DEFINITIONS],
            ["monitor_workbook"],
        )

    def test_schema_rejects_unknown_or_unsafe_configuration(self) -> None:
        unknown = BASELINE_CONFIGURATION.model_dump(mode="json")
        unknown["formula"] = "__import__('os').system('unsafe')"
        with self.assertRaises(ValidationError):
            validate_configuration(unknown)

        invalid_airport = BASELINE_CONFIGURATION.model_dump(mode="json")
        invalid_airport["vat"]["airports"] = ["DME", "bad"]
        with self.assertRaisesRegex(ValueError, "uppercase IATA"):
            validate_configuration(invalid_airport)

        unknown_variable = BASELINE_CONFIGURATION.model_dump(mode="json")
        unknown_variable["operations"]["catering"]["parts"][0]["initial"] = {
            "kind": "variable",
            "name": "arbitrary_python",
        }
        with self.assertRaisesRegex(ValueError, "Неизвестная variable"):
            validate_configuration(unknown_variable)

        unknown_lookup = BASELINE_CONFIGURATION.model_dump(mode="json")
        unknown_lookup["operations"]["ano"]["parts"][0]["initial"]["name"] = "arbitrary_query"
        with self.assertRaisesRegex(ValueError, "Неизвестный lookup"):
            validate_configuration(unknown_lookup)

        division_by_zero = BASELINE_CONFIGURATION.model_dump(mode="json")
        division_by_zero["operations"]["ano"]["parts"][1]["operations"][0]["operand"]["value"] = 0
        with self.assertRaisesRegex(ValueError, "division by zero"):
            validate_configuration(division_by_zero)

        unknown_operation = BASELINE_CONFIGURATION.model_dump(mode="json")
        unknown_operation["operations"]["ano"]["parts"][1]["operations"][0]["operation"] = "eval"
        with self.assertRaises(ValidationError):
            validate_configuration(unknown_operation)

        invalid_condition = BASELINE_CONFIGURATION.model_dump(mode="json")
        invalid_condition["operations"]["vat"]["parts"][0]["condition"]["any_of"][0]["all_of"][1]["right"] = {
            "kind": "constant",
            "value": "DME",
        }
        with self.assertRaisesRegex(ValueError, "collection"):
            validate_configuration(invalid_condition)

        invalid_type = BASELINE_CONFIGURATION.model_dump(mode="json")
        invalid_type["operations"]["ano"]["parts"][1]["initial"] = {"kind": "constant", "value": "not-a-number"}
        with self.assertRaisesRegex(ValueError, "numeric"):
            validate_configuration(invalid_type)

        non_finite = BASELINE_CONFIGURATION.model_dump(mode="json")
        non_finite["fuel"]["consumption_tons_per_hour"] = float("nan")
        with self.assertRaises(ValidationError):
            validate_configuration(non_finite)

    def test_definition_registers_only_explicit_variables_and_primitives(self) -> None:
        self.assertTrue(
            {"flight_time", "distance", "passengers", "aircraft", "departure", "arrival", "line_type", "is_techstop"}
            .issubset(REGISTERED_VARIABLE_NAMES)
        )
        self.assertEqual(ALLOWED_PRIMITIVE_NAMES, {"add", "subtract", "multiply", "divide", "round", "sum"})
        self.assertNotIn("eval", ALLOWED_PRIMITIVE_NAMES)
        self.assertNotIn("exec", ALLOWED_PRIMITIVE_NAMES)

    def test_calculation_consumes_validated_configuration_without_changing_default(self) -> None:
        state = {
            "routes": [{"key": "AAA-BBB", "flight_time": 2, "distance": 100}],
            "international_airports": {},
            "imported_tariffs": [
                {"airport": "AAA", "service": "КЕРОСИН", "rate": 100},
                {"airport": "AAA", "service": "ЗАПРАВКА ВС", "rate": 20},
                {"airport": "AAA", "service": "АНО АД", "rate": 1000},
            ],
            "manual_tariffs": [],
            "fuel_prices": [],
            "scenario_rates": {"ГБ 2026": {"738": [10, 20, 30]}},
            "aircraft_multipliers": {"738": 1},
        }
        request = CalculationRequest.model_validate(
            {
                "legs": [{"id": "one", "departure": "AAA", "arrival": "BBB", "aircraft": "738", "passengers": 0}],
                "settings": {"scenario": "ГБ 2026", "fuel_source": "ЦРТ", "catering": False},
            }
        )
        custom_payload = BASELINE_CONFIGURATION.model_dump(mode="json")
        custom_payload["fuel"]["consumption_tons_per_hour"] = 3.0
        custom = validate_configuration(custom_payload)

        dataset = CostMonitorDataset.from_state(state)
        baseline_result = calculate(dataset, request)
        custom_result = calculate(dataset, request, custom)

        self.assertEqual(baseline_result["legs"][0]["components"]["fuel"], 648.0)
        self.assertEqual(custom_result["legs"][0]["components"]["fuel"], 720.0)

    def test_default_production_state_calculates_without_monitor_workbook_source(self) -> None:
        state = build_default_state(Path("sources"))
        state.update(
            {
                "routes": [{"key": "AAA-BBB", "flight_time": 2, "distance": 100}],
                "imported_tariffs": [
                    {"airport": "AAA", "service": "КЕРОСИН", "rate": 100},
                    {"airport": "AAA", "service": "ЗАПРАВКА ВС", "rate": 20},
                    {"airport": "AAA", "service": "АНО АД", "rate": 1000},
                ],
            }
        )
        request = CalculationRequest.model_validate(
            {"legs": [{"id": "one", "departure": "AAA", "arrival": "BBB", "aircraft": "738"}]}
        )

        result = calculate(CostMonitorDataset.from_state(state), request)

        self.assertEqual([source["id"] for source in state["source_configs"]], ["srv", "fuel_registry"])
        self.assertEqual(result["legs"][0]["route"], "AAA-BBB")

    def test_legacy_v1_payload_is_upgraded_without_preserving_double_sources(self) -> None:
        legacy = {
            "schema_version": "1.0",
            "fuel": {"consumption_tons_per_hour": 2.7},
            "ano": {"route_rate_per_100_km": 1666.6},
            "catering": {"base_units": 6, "base_unit_rate": 1500, "passenger_surcharge": 500},
            "vat": {"rate": 0.1, "airports": ["DME", "SVO", "VKO"]},
            "ground": {
                "split_divisor": 2,
                "stairs_units": 2,
                "telebridge_minutes": 90,
                "transport_passenger_block": 100,
                "fire_truck_rate": 25132,
            },
            "initial_data": {"aircraft_multipliers": {"738": 99}, "scenario_rates": {"Old": {"738": [1, 2, 3]}}},
            "source_bindings": [],
        }

        upgraded = validate_configuration(legacy)

        self.assertEqual(upgraded.schema_version, "2.0")
        self.assertFalse(hasattr(upgraded, "initial_data"))
        self.assertFalse(hasattr(upgraded, "source_bindings"))
        self.assertEqual(upgraded.operations.catering.aggregation, "sum")


if __name__ == "__main__":
    unittest.main()
