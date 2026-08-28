from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.core.config import Settings
from app.core.store import JsonStore


class JsonStoreTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
