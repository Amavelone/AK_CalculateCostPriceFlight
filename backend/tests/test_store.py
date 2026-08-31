from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.core.config import Settings
from app.modules.cost_monitor.repository import CostMonitorRepository
from app.modules.cost_monitor.store import JsonStore


class JsonStoreTests(unittest.TestCase):
    def test_json_store_implements_module_repository_audit_and_revision_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings = Settings(project_root=root, data_dir=root / "data", default_source_dir=root / "sources")
            repository: CostMonitorRepository = JsonStore(settings)

            def change_data(state: dict) -> int:
                repository.append_audit(state, "adapter_boundary_checked", "srv")
                return repository.mark_calculation_data_changed(state)

            revision = repository.mutate(change_data)
            state = repository.read()

        self.assertEqual(revision, 1)
        self.assertEqual(state["data_revision"], 1)
        self.assertEqual(state["audit_log"][-1]["action"], "adapter_boundary_checked")

    def test_draft_survives_store_recreation_without_changing_data_revision(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings = Settings(
                project_root=root,
                data_dir=root / "data",
                default_source_dir=root / "sources",
            )
            store = JsonStore(settings)

            def save_draft(state: dict) -> None:
                state["drafts"]["browser-draft"] = {"calculation": {"legs": []}}

            store.mutate(save_draft)
            restored = JsonStore(settings).read()

            self.assertEqual(restored["drafts"]["browser-draft"]["calculation"]["legs"], [])
            self.assertEqual(restored["data_revision"], 0)
            self.assertIsNone(restored["data_updated_at"])

    def test_existing_store_with_imported_data_gets_initial_revision(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings = Settings(
                project_root=root,
                data_dir=root / "data",
                default_source_dir=root / "sources",
            )
            store = JsonStore(settings)

            def create_legacy_state(state: dict) -> None:
                state["imported_tariffs"] = [{"airport": "AAA", "service": "ВОДА", "rate": 100}]
                state["routes"] = [{"key": "AAA-BBB", "flight_time": 1, "distance": 100}]
                state["source_configs"][0]["last_updated"] = "2026-08-28T10:00:00+00:00"
                state.pop("data_revision", None)
                state.pop("data_updated_at", None)

            store.mutate(create_legacy_state)
            migrated = JsonStore(settings).read()

            self.assertEqual(migrated["data_revision"], 1)
            self.assertEqual(migrated["data_updated_at"], "2026-08-28T10:00:00+00:00")

    def test_migration_removes_workbook_source_without_changing_calculation_data(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings = Settings(
                project_root=root,
                data_dir=root / "data",
                default_source_dir=root / "sources",
            )
            store = JsonStore(settings)

            def add_legacy_source(state: dict) -> None:
                legacy_source = {
                    "id": "monitor_workbook",
                    "parser": "monitor_workbook",
                    "last_updated": None,
                }
                state["source_configs"].insert(1, legacy_source)
                state["imported_tariffs"] = [{"airport": "KJA", "service": "ВОДА", "rate": 100}]

            store.mutate(add_legacy_source)
            migrated = JsonStore(settings).read()

            self.assertEqual([source["id"] for source in migrated["source_configs"]], ["srv", "fuel_registry"])
            self.assertEqual(migrated["imported_tariffs"], [{"airport": "KJA", "service": "ВОДА", "rate": 100}])

    def test_legacy_store_gets_immutable_active_configuration_v1(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings = Settings(
                project_root=root,
                data_dir=root / "data",
                default_source_dir=root / "sources",
            )
            store = JsonStore(settings)

            def remove_configuration_lifecycle(state: dict) -> None:
                for key in (
                    "configuration_versions",
                    "configuration_drafts",
                    "active_configuration_version",
                    "next_configuration_version",
                ):
                    state.pop(key, None)

            store.mutate(remove_configuration_lifecycle)
            migrated = JsonStore(settings).read()

            self.assertEqual(migrated["active_configuration_version"], 1)
            self.assertEqual(migrated["next_configuration_version"], 2)
            self.assertEqual(migrated["configuration_drafts"], {})
            self.assertEqual(migrated["configuration_versions"][0]["state"], "active")


if __name__ == "__main__":
    unittest.main()
