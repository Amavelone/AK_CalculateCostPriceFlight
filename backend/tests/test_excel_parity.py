from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

from app.modules.cost_monitor.calculation import calculate
from app.modules.cost_monitor.exports import build_export_snapshot
from app.modules.cost_monitor.records import CostMonitorDataset, CostMonitorReferenceSnapshot
from app.modules.cost_monitor.schemas import CalculationRequest

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "excel_cost_monitor_baseline.json"
MONEY_COMPONENTS_WITH_DETAILS = ("fuel", "ground", "ano", "catering")


def load_fixture() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def build_state(fixture: dict[str, Any]) -> dict[str, Any]:
    normalized = fixture["normalized_state"]
    tariffs = [
        {"airport": airport, "service": service, "rate": rate}
        for airport, services in normalized["tariff_rates"].items()
        for service, rate in services.items()
    ]
    return {
        "data_revision": 1,
        "routes": normalized["routes"],
        "imported_tariffs": tariffs,
        "manual_tariffs": [],
        "fuel_prices": [],
        "other_costs": normalized["other_costs"],
    }


class ExcelParityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = load_fixture()
        self.request = CalculationRequest.model_validate(self.fixture["request"])
        self.state = build_state(self.fixture)
        self.result = calculate(
            CostMonitorDataset.from_state(self.state),
            self.request,
            reference_data=CostMonitorReferenceSnapshot.from_legacy_state(self.state),
        )

    def test_approved_five_leg_scenario_matches_excel_cached_values(self) -> None:
        expected_legs = self.fixture["expected_excel_rows"]
        self.assertEqual(len(self.result["legs"]), len(expected_legs))

        for actual, expected in zip(self.result["legs"], expected_legs, strict=True):
            with self.subTest(route=expected["route"]):
                self.assertEqual(actual["route"], expected["route"])
                # API намеренно возвращает параметры маршрута с точностью интерфейса,
                # а денежные итоги выше рассчитываются с полной точностью.
                self.assertEqual(actual["flight_time"], round(expected["flight_time"], 3))
                self.assertEqual(actual["fuel_tons"], round(expected["fuel_tons"], 3))

                for component in MONEY_COMPONENTS_WITH_DETAILS:
                    raw_amount = sum(item["amount"] for item in actual["details"][component])
                    self.assertAlmostEqual(raw_amount, expected["components"][component], delta=1e-6)

                self.assertAlmostEqual(actual["components"]["vat"], expected["components"]["vat"], delta=0.0051)
                for margin in ("m1", "m2", "m3"):
                    self.assertAlmostEqual(actual["components"][margin], expected["components"][margin], delta=0.0051)
                    self.assertAlmostEqual(actual["totals"][margin], expected["totals"][margin], delta=0.0051)

        for margin, expected in self.fixture["expected_excel_total"].items():
            self.assertAlmostEqual(self.result["total"][margin], expected, delta=0.0051)

    def test_baseline_keeps_intentional_missing_route_warning(self) -> None:
        self.assertEqual(
            self.result["warnings"],
            ["Маршрут OVB-HMA не найден в ИШР: налет принят равным 0."],
        )

    def test_legacy_unused_source_configuration_does_not_affect_calculation(self) -> None:
        state_with_legacy_source = build_state(self.fixture)
        state_with_legacy_source["source_configs"] = [{"id": "obsolete", "parser": "unsupported"}]

        result_with_legacy_source = calculate(
            CostMonitorDataset.from_state(state_with_legacy_source),
            self.request,
            reference_data=CostMonitorReferenceSnapshot.from_legacy_state(state_with_legacy_source),
        )

        self.assertEqual(
            {key: value for key, value in result_with_legacy_source.items() if key != "calculated_at"},
            {key: value for key, value in self.result.items() if key != "calculated_at"},
        )

    def test_calculation_and_export_contract_shape_is_frozen(self) -> None:
        self.assertEqual(
            set(self.result),
            {
                "calculated_at",
                "legs",
                "total",
                "warnings",
                "status",
                "diagnostics",
                "data_snapshot",
                "config_version",
                "configuration_state",
                "reference_version",
                "reference_state",
                "trace",
            },
        )
        self.assertEqual(
            set(self.result["legs"][0]),
            {
                "id",
                "route",
                "departure",
                "arrival",
                "aircraft",
                "passengers",
                "flight_time",
                "distance",
                "fuel_tons",
                "line_type",
                "is_techstop",
                "components",
                "totals",
                "details",
                "warnings",
                "status",
                "diagnostics",
            },
        )
        snapshot = build_export_snapshot(self.request, self.result)
        self.assertEqual(set(snapshot), {"schema_version", "exported_at", "calculation"})
        self.assertEqual(
            set(snapshot["calculation"]),
            {"config_version", "configuration_state", "reference_version", "reference_state", "data_snapshot", "configuration", "legs", "totals", "warnings", "trace"},
        )
        self.assertEqual(snapshot["schema_version"], "1.0")
        self.assertEqual(snapshot["calculation"]["config_version"], 1)
        self.assertEqual(snapshot["calculation"]["reference_version"], 1)
        self.assertEqual(snapshot["calculation"]["trace"]["data_revision"], 1)


if __name__ == "__main__":
    unittest.main()
