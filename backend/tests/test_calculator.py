from __future__ import annotations

import unittest

from app.modules.cost_monitor.calculation import calculate
from app.modules.cost_monitor.configuration import BASELINE_CONFIGURATION, validate_configuration
from app.modules.cost_monitor.records import CostMonitorDataset, CostMonitorReferenceSnapshot
from app.modules.cost_monitor.schemas import CalculationRequest


class CalculatorTests(unittest.TestCase):
    def calculate(self, state: dict, request: CalculationRequest) -> dict:
        configuration_payload = BASELINE_CONFIGURATION.model_dump(mode="json")
        configuration_payload["overrides"]["aircraft_multipliers"] = {"738": 1}
        configuration_payload["overrides"]["scenario_rates"] = {"ГБ 2026": {"738": [10, 20, 30]}}
        return calculate(
            CostMonitorDataset.from_state(state),
            request,
            validate_configuration(configuration_payload),
            reference_data=CostMonitorReferenceSnapshot.from_legacy_state(state),
        )

    def base_state(self) -> dict:
        return {
            "routes": [
                {"key": "AAA-BBB", "flight_time": 2, "distance": 100},
                {"key": "BBB-CCC", "flight_time": 1, "distance": 200},
            ],
            "imported_tariffs": [
                {"airport": "AAA", "service": "КЕРОСИН", "rate": 100},
                {"airport": "AAA", "service": "КЕРОСИН", "rate": 999},
                {"airport": "AAA", "service": "ЗАПРАВКА ВС", "rate": 20},
                {"airport": "AAA", "service": "АНО АД", "rate": 1000},
                {"airport": "BBB", "service": "КЕРОСИН", "rate": 80},
                {"airport": "BBB", "service": "ЗАПРАВКА ВС", "rate": 20},
                {"airport": "BBB", "service": "АНО АД", "rate": 1000},
            ],
            "manual_tariffs": [],
            "fuel_prices": [],
        }

    def test_first_tariff_row_is_used_and_all_legs_are_summed(self) -> None:
        state = self.base_state()
        request = CalculationRequest.model_validate(
            {
                "legs": [
                    {"id": "one", "departure": "AAA", "arrival": "BBB", "aircraft": "738", "passengers": 0},
                    {"id": "two", "departure": "BBB", "arrival": "CCC", "aircraft": "738", "passengers": 0},
                ],
                "settings": {"scenario": "ГБ 2026", "fuel_source": "ЦРТ", "catering": False},
            }
        )

        result = self.calculate(state, request)

        self.assertEqual(result["legs"][0]["components"]["fuel"], 648.0)
        self.assertEqual(result["legs"][0]["components"]["ano"], 2666.6)
        self.assertEqual(result["total"]["m2"], 85917.8)

    def test_catering_control_only_changes_passenger_component(self) -> None:
        state = self.base_state()
        base_payload = {
            "legs": [{"id": "one", "departure": "AAA", "arrival": "BBB", "aircraft": "738", "passengers": 17}],
            "settings": {"scenario": "ГБ 2026", "fuel_source": "ЦРТ", "catering": False},
        }
        disabled = self.calculate(state, CalculationRequest.model_validate(base_payload))
        base_payload["settings"]["catering"] = True
        enabled = self.calculate(state, CalculationRequest.model_validate(base_payload))

        self.assertEqual(disabled["legs"][0]["components"]["catering"], 9000)
        self.assertEqual(enabled["legs"][0]["components"]["catering"], 17500)
        self.assertEqual(enabled["total"]["m2"] - disabled["total"]["m2"], 8500)

    def test_result_carries_active_data_revision(self) -> None:
        state = self.base_state()
        state["data_revision"] = 12
        request = CalculationRequest.model_validate(
            {
                "legs": [{"id": "one", "departure": "AAA", "arrival": "BBB", "aircraft": "738", "passengers": 0}],
                "settings": {"scenario": "ГБ 2026", "fuel_source": "ЦРТ", "catering": False},
            }
        )

        result = self.calculate(state, request)

        self.assertEqual(result["data_snapshot"]["revision"], 12)
        self.assertEqual(result["config_version"], 1)
        self.assertEqual(result["reference_version"], 1)
        self.assertEqual(result["trace"]["data_revision"], 12)
        self.assertEqual(
            {step["stage"] for step in result["trace"]["legs"][0]["steps"]},
            {"input", "lookup", "parameters", "operation", "result"},
        )

    def test_ak_uses_fuel_registry_price(self) -> None:
        state = self.base_state()
        state["fuel_prices"] = [{"airport": "AAA", "price": 1000}]
        request = CalculationRequest.model_validate(
            {
                "legs": [{"id": "one", "departure": "AAA", "arrival": "BBB", "aircraft": "738", "passengers": 0}],
                "settings": {"scenario": "ГБ 2026", "fuel_source": "АК", "catering": False},
            }
        )

        result = self.calculate(state, request)

        self.assertEqual(result["legs"][0]["components"]["fuel"], 5400)
        self.assertEqual(result["legs"][0]["details"]["fuel"][0]["service"], "Керосин АК")

    def test_techstop_uses_dedicated_ground_block(self) -> None:
        state = self.base_state()
        state["imported_tariffs"] = [
            {"airport": "AAA", "service": service, "rate": 100}
            for service in ("ВЗЛЕТ-ПОСАДКА", "ТРАНСПБЕЗОП", "ПРИЕМ-ВЫПУСК", "БУКСИРОВКА", "ТРАП")
        ]
        request = CalculationRequest.model_validate(
            {
                "legs": [{"id": "techstop", "departure": "AAA", "arrival": "BBB", "aircraft": "738", "passengers": 0}],
                "settings": {"scenario": "ГБ 2026", "fuel_source": "ЦРТ", "techstop_leg_id": "techstop", "catering": False},
            }
        )

        result = self.calculate(state, request)

        self.assertTrue(result["legs"][0]["is_techstop"])
        self.assertEqual(result["legs"][0]["components"]["ground"], 13066)

    def test_missing_reference_data_is_reported_without_failing_calculation(self) -> None:
        state = self.base_state()
        request = CalculationRequest.model_validate(
            {
                "legs": [{"id": "one", "departure": "CCC", "arrival": "DDD", "aircraft": "738", "passengers": 0}],
                "settings": {"scenario": "ГБ 2026", "fuel_source": "АК", "catering": False},
            }
        )

        result = self.calculate(state, request)

        self.assertEqual(result["legs"][0]["flight_time"], 0)
        self.assertTrue(any("Маршрут CCC-DDD не найден" in warning for warning in result["warnings"]))
        self.assertTrue(any("Не найдена цена керосина АК" in warning for warning in result["warnings"]))
        self.assertEqual(result["status"], "degraded")
        self.assertTrue(
            {"missing_route", "missing_fuel_price", "missing_ano_rate", "GROUND_TARIFF_MISSING"}
            .issubset({item["code"] for item in result["diagnostics"]})
        )

    def test_missing_required_ground_tariff_keeps_zero_and_degrades_result(self) -> None:
        state = self.base_state()
        request = CalculationRequest.model_validate(
            {
                "legs": [{"id": "one", "departure": "AAA", "arrival": "BBB", "aircraft": "738", "passengers": 0}],
                "settings": {"scenario": "ГБ 2026", "fuel_source": "ЦРТ", "catering": False},
            }
        )

        result = self.calculate(state, request)

        self.assertEqual(result["legs"][0]["components"]["ground"], 0)
        self.assertEqual(result["status"], "degraded")
        ground_diagnostics = [item for item in result["diagnostics"] if item["code"] == "GROUND_TARIFF_MISSING"]
        self.assertTrue(any(item["reference"] == "AAA/ПРИЕМ-ВЫПУСК" for item in ground_diagnostics))
        self.assertFalse(any("ПАССАЖИР(М)" in (item["reference"] or "") for item in ground_diagnostics))

    def test_release_runtime_is_vvl_even_if_legacy_state_contains_mvl_markers(self) -> None:
        state = self.base_state()
        state["international_airports"] = {"AAA": True, "BBB": True}
        request = CalculationRequest.model_validate(
            {
                "legs": [{"id": "one", "departure": "AAA", "arrival": "BBB", "aircraft": "738", "passengers": 5}],
                "settings": {"scenario": "ГБ 2026", "fuel_source": "ЦРТ", "catering": False},
            }
        )

        result = self.calculate(state, request)

        self.assertEqual(result["legs"][0]["line_type"], "ВВЛ")
        self.assertFalse(any("М)" in item["service"] for item in result["legs"][0]["details"]["ground"]))

    def test_any_number_of_legs_is_accepted(self) -> None:
        state = self.base_state()
        request = CalculationRequest.model_validate(
            {
                "legs": [
                    {"id": f"leg-{index}", "departure": "AAA", "arrival": "BBB", "aircraft": "738", "passengers": 0}
                    for index in range(7)
                ],
                "settings": {"scenario": "ГБ 2026", "fuel_source": "ЦРТ", "catering": False},
            }
        )

        result = self.calculate(state, request)

        self.assertEqual(len(result["legs"]), 7)
        self.assertGreater(result["total"]["m2"], result["legs"][0]["totals"]["m2"])


if __name__ == "__main__":
    unittest.main()
