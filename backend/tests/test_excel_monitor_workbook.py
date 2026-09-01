from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

from openpyxl import load_workbook

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "excel_cost_monitor_baseline.json"


class ExcelMonitorWorkbookTests(unittest.TestCase):
    """Optional local gate proving the approved workbook still matches the golden fixture."""

    def test_supplied_monitor_cached_values_match_excel_golden_fixture(self) -> None:
        workbook_path = os.getenv("EXCEL_MONITOR_PATH")
        if not workbook_path:
            self.skipTest("EXCEL_MONITOR_PATH is required for the local approved-workbook gate")
        path = Path(workbook_path)
        self.assertTrue(path.is_file(), f"Workbook not found: {path}")
        workbook = load_workbook(path, data_only=True, read_only=True)
        sheet = workbook["РАСЧЕТ"]
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        columns = {"route": "C", "flight_time": "E", "fuel_tons": "F", "fuel": "G", "ground": "H", "ano": "I", "catering": "J", "vat": "K", "m1": "L", "m2": "M", "m3": "N"}
        for row, expected in enumerate(fixture["expected_excel_rows"], start=2):
            with self.subTest(route=expected["route"]):
                self.assertEqual(sheet[f"{columns['route']}{row}"].value, expected["route"])
                self.assertAlmostEqual(sheet[f"{columns['flight_time']}{row}"].value, expected["flight_time"])
                self.assertAlmostEqual(sheet[f"{columns['fuel_tons']}{row}"].value, expected["fuel_tons"])
                for component in ("fuel", "ground", "ano", "catering", "vat", "m1", "m2", "m3"):
                    self.assertAlmostEqual(sheet[f"{columns[component]}{row}"].value, expected["components"][component])
        expected_total = fixture["expected_excel_total"]
        self.assertAlmostEqual(sheet["O7"].value, expected_total["m1"])
        self.assertAlmostEqual(sheet["P7"].value, expected_total["m2"])
        self.assertAlmostEqual(sheet["Q7"].value, expected_total["m3"])


if __name__ == "__main__":
    unittest.main()
