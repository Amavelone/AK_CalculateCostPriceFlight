from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from app.services.sources import mark_source_error, refresh_source, tariffs_for_view, workbook_preview


class WorkbookPreviewTests(unittest.TestCase):
    def test_uses_detected_header_and_requested_worksheet(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "registry.xlsx"
            workbook = Workbook()
            workbook.active.title = "Титул"
            registry = workbook.create_sheet("Реестр")
            registry.append(["Служебная строка"])
            registry.append(["Дата выгрузки", "2026-08-28"])
            registry.append(["Партнер", "Валюта", "Цена"])
            registry.append(["Тестовый поставщик", "RUB", 100])
            registry.append(["Другой поставщик", "USD", 120])
            workbook.save(path)

            preview = workbook_preview(path, sheet_name="Реестр", row_limit=2)

            self.assertEqual(preview["sheet"], "Реестр")
            self.assertEqual(preview["sheets"], ["Титул", "Реестр"])
            self.assertEqual(preview["preview"][0]["Партнер"], "Тестовый поставщик")
            self.assertEqual(preview["preview"][1]["Цена"], 120)

    def test_reports_unknown_worksheet(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "book.xlsx"
            Workbook().save(path)

            with self.assertRaisesRegex(ValueError, "Лист не найден"):
                workbook_preview(path, sheet_name="Нет такого листа")

    def test_manual_service_is_retained_and_marked_as_conflict(self) -> None:
        state = {
            "imported_tariffs": [{"id": "file-1", "airport": "AAA", "service": "ВОДА", "rate": 100, "source": "file"}],
            "manual_tariffs": [{"id": "manual-1", "airport": "AAA", "service": "ВОДА", "rate": 200, "source": "manual"}],
        }

        tariffs = tariffs_for_view(state)

        self.assertFalse(tariffs[0]["conflict"])
        self.assertTrue(tariffs[1]["conflict"])
        self.assertEqual(tariffs[1]["source"], "manual")

    def test_missing_source_can_be_marked_with_actionable_error(self) -> None:
        state = {
            "source_configs": [
                {
                    "id": "srv",
                    "directory": "Z:/missing-source-directory",
                    "mask": "7480_srv*.xlsx",
                    "parser": "srv_tariffs",
                    "last_status": "ready",
                }
            ]
        }

        with self.assertRaises(FileNotFoundError):
            refresh_source(state, "srv", "2026-08-28T10:00:00+00:00")
        source = mark_source_error(state, "srv", "Директория не найдена", "2026-08-28T10:00:00+00:00")

        self.assertEqual(source["last_status"], "error")
        self.assertEqual(source["last_error"], "Директория не найдена")


if __name__ == "__main__":
    unittest.main()
