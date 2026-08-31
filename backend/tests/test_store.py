from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.core.config import Settings
from app.modules.cost_monitor.baselines import baseline_manual_tariffs
from app.modules.cost_monitor.reference_data.defaults import BASELINE_REFERENCE_DATA
from app.modules.cost_monitor.repository import CostMonitorRepository
from app.modules.cost_monitor.store import JsonStore


class JsonStoreTests(unittest.TestCase):
    def test_fresh_production_store_uses_checked_in_reference_baselines(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings = Settings(project_root=root, data_dir=root / "data", default_source_dir=root / "sources")
            state = JsonStore(settings).read()

        reference = state["reference_data_versions"][0]["reference_data"]
        self.assertEqual(reference, BASELINE_REFERENCE_DATA.model_dump(mode="json"))
        self.assertEqual(state["manual_tariffs"], baseline_manual_tariffs())
        self.assertEqual(len(reference["routes"]), 500)
        self.assertEqual(len(reference["airport_other_costs"]), 45)
        self.assertEqual(len(state["manual_tariffs"]), 10)
        self.assertEqual([item["airport"] for item in state["manual_tariffs"][:2]], ["=EL", "=EL"])
        self.assertNotIn("international_airports", state)
        self.assertNotIn("aircraft_multipliers", state)
        self.assertNotIn("scenario_rates", state)
        self.assertNotIn("routes", state)
        self.assertNotIn("other_costs", state)
        self.assertEqual(state["active_reference_data_version"], 1)

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

    def test_legacy_workbook_migration_preserves_populated_data_and_manual_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings = Settings(project_root=root, data_dir=root / "data", default_source_dir=root / "sources")
            store = JsonStore(settings)

            def create_legacy_state(state: dict) -> None:
                for key in (
                    "reference_data_versions",
                    "reference_data_drafts",
                    "active_reference_data_version",
                    "next_reference_data_version",
                ):
                    state.pop(key, None)
                state["routes"] = [{"key": "CUSTOM-ROUTE", "flight_time": 1, "distance": 2}]
                state["other_costs"] = {"CUSTOM": 123.0}
                state["manual_tariffs"] = [
                    {"airport": "=EL", "service": "КЕРОСИН", "rate": 999.0, "legacy_manual": True},
                ]
                state["international_airports"] = {"OLD": True}
                state["aircraft_multipliers"] = {"738": 1.0}
                state["scenario_rates"] = {"Old": {"738": [1, 2, 3]}}
                state.pop("release_v1_workbook_ownership_migrated", None)

            store.mutate(create_legacy_state)
            migrated = JsonStore(settings).read()

        reference = migrated["reference_data_versions"][0]["reference_data"]
        self.assertEqual(reference["routes"], [{"departure": "CUSTOM", "arrival": "ROUTE", "flight_time": 1.0, "distance": 2.0, "source_row": None}])
        self.assertEqual(reference["airport_other_costs"], [{"airport": "CUSTOM", "amount": 123.0}])
        manual_by_key = {(item["airport"], item["service"]): item for item in migrated["manual_tariffs"]}
        self.assertEqual(len(manual_by_key), 10)
        self.assertEqual(manual_by_key[("=EL", "КЕРОСИН")]["rate"], 999.0)
        self.assertNotIn("legacy_manual", manual_by_key[("=EL", "КЕРОСИН")])
        self.assertTrue(migrated["release_v1_workbook_ownership_migrated"])
        self.assertEqual(migrated["configuration_versions"][0]["version"], 1)
        overrides = migrated["configuration_versions"][0]["configuration"]["overrides"]
        self.assertEqual(overrides["aircraft_multipliers"]["738"], 79.015)
        self.assertNotIn("international_airports", migrated)
        self.assertNotIn("aircraft_multipliers", migrated)
        self.assertNotIn("scenario_rates", migrated)
        self.assertNotIn("routes", migrated)
        self.assertNotIn("other_costs", migrated)

    def test_reference_migration_seeds_only_empty_legacy_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings = Settings(project_root=root, data_dir=root / "data", default_source_dir=root / "sources")
            store = JsonStore(settings)

            def create_partial_legacy_state(state: dict) -> None:
                for key in (
                    "reference_data_versions",
                    "reference_data_drafts",
                    "active_reference_data_version",
                    "next_reference_data_version",
                ):
                    state.pop(key, None)
                state["routes"] = [{"key": "CUSTOM-ONLY", "flight_time": 1, "distance": 2}]
                state["other_costs"] = {}

            store.mutate(create_partial_legacy_state)
            migrated = JsonStore(settings).read()

        reference = migrated["reference_data_versions"][0]["reference_data"]
        self.assertEqual(reference["routes"][0]["departure"], "CUSTOM")
        self.assertEqual(reference["routes"][0]["arrival"], "ONLY")
        self.assertEqual(len(reference["airport_other_costs"]), 45)


if __name__ == "__main__":
    unittest.main()
