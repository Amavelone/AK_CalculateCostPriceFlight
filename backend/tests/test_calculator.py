from __future__ import annotations

import unittest

from app.modules.cost_monitor.calculation import calculate
from app.modules.cost_monitor.schemas import CalculationRequest


class CalculatorTests(unittest.TestCase):
    def base_state(self) -> dict:
        return {
            "routes": [
                {"key": "AAA-BBB", "flight_time": 2, "distance": 100},
                {"key": "BBB-CCC", "flight_time": 1, "distance": 200},
            ],
            "international_airports": {},
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
            "scenario_rates": {"ГБ 2026": {"738": [10, 20, 30]}},
            "aircraft_multipliers": {"738": 1},
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

        result = calculate(state, request)

        self.assertEqual(result["legs"][0]["components"]["fuel"], 648.0)
        self.assertEqual(result["legs"][0]["components"]["ano"], 2666.6)
        self.assertEqual(result["total"]["m2"], 85917.8)

    def test_catering_control_only_changes_passenger_component(self) -> None:
        state = self.base_state()
        base_payload = {
            "legs": [{"id": "one", "departure": "AAA", "arrival": "BBB", "aircraft": "738", "passengers": 17}],
            "settings": {"scenario": "ГБ 2026", "fuel_source": "ЦРТ", "catering": False},
        }
        disabled = calculate(state, CalculationRequest.model_validate(base_payload))
        base_payload["settings"]["catering"] = True
        enabled = calculate(state, CalculationRequest.model_validate(base_payload))

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

        self.assertEqual(calculate(state, request)["data_snapshot"]["revision"], 12)

    def test_ak_uses_fuel_registry_price(self) -> None:
        state = self.base_state()
        state["fuel_prices"] = [{"airport": "AAA", "price": 1000}]
        request = CalculationRequest.model_validate(
            {
                "legs": [{"id": "one", "departure": "AAA", "arrival": "BBB", "aircraft": "738", "passengers": 0}],
                "settings": {"scenario": "ГБ 2026", "fuel_source": "АК", "catering": False},
            }
        )

        result = calculate(state, request)

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

        result = calculate(state, request)

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

        result = calculate(state, request)

        self.assertEqual(result["legs"][0]["flight_time"], 0)
        self.assertTrue(any("Маршрут CCC-DDD не найден" in warning for warning in result["warnings"]))
        self.assertTrue(any("Не найдена цена керосина АК" in warning for warning in result["warnings"]))

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

        result = calculate(state, request)

        self.assertEqual(len(result["legs"]), 7)
        self.assertGreater(result["total"]["m2"], result["legs"][0]["totals"]["m2"])


if __name__ == "__main__":
    unittest.main()
