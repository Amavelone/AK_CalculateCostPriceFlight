from __future__ import annotations

import copy
import math
import unittest
from pathlib import Path
from unittest.mock import patch

from app.modules.cost_monitor import api as cost_api
from app.modules.cost_monitor.configuration import ConfigurationService, JsonConfigurationRepository
from app.modules.cost_monitor.reference_data import ReferenceDataService, ReferenceDataValidationError
from app.modules.cost_monitor.reference_data.repository import JsonReferenceDataRepository
from app.modules.cost_monitor.schemas import CalculationRequest
from app.modules.cost_monitor.store import build_default_state, utc_now


class MemoryReferenceStore:
    def __init__(self, state: dict) -> None:
        self.state = copy.deepcopy(state)

    def read(self) -> dict:
        return copy.deepcopy(self.state)

    def mutate(self, operation):
        return copy.deepcopy(operation(self.state))

    def append_audit(self, state: dict, action: str, detail: str) -> None:
        state.setdefault("audit_log", []).append({"at": utc_now(), "action": action, "detail": detail})

    def mark_calculation_data_changed(self, state: dict) -> int:
        state["data_revision"] = int(state.get("data_revision", 0)) + 1
        state["data_updated_at"] = utc_now()
        return state["data_revision"]


class ReferenceDataServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        state = build_default_state(Path("sources"))
        state["imported_tariffs"] = [{"airport": "AAA", "service": "КЕРОСИН", "rate": 100}]
        state["reference_data_versions"][0]["reference_data"] = {
            "schema_version": "1.0",
            "routes": [{"departure": "AAA", "arrival": "BBB", "distance": 100, "flight_time": 2}],
            "airport_other_costs": [{"airport": "AAA", "amount": 10}],
        }
        self.store = MemoryReferenceStore(state)
        self.service = ReferenceDataService(JsonReferenceDataRepository(self.store))
        self.configuration_service = ConfigurationService(JsonConfigurationRepository(self.store))

    @staticmethod
    def request() -> CalculationRequest:
        return CalculationRequest.model_validate(
            {
                "legs": [{"id": "one", "departure": "AAA", "arrival": "BBB", "aircraft": "738", "passengers": 0}],
                "settings": {"scenario": "ГБ 2026", "fuel_source": "ЦРТ", "catering": False},
            }
        )

    def test_draft_compare_preview_activate_and_rollback_keep_live_revision(self) -> None:
        initial_revision = self.store.state["data_revision"]
        draft = self.service.create_draft()
        candidate = draft["reference_data"]
        candidate["routes"][0]["flight_time"] = 3
        candidate["airport_other_costs"][0]["amount"] = 20
        updated = self.service.update_draft(draft["version"], candidate)

        self.assertEqual(self.service.active()["version"], 1)
        self.assertEqual(self.service.active()["reference_data"].routes[0].flight_time, 2)
        self.assertEqual(updated["validation_status"], "valid")
        self.assertEqual(self.service.validate_draft(draft["version"])["validation_status"], "valid")
        changes = self.service.compare(1, draft["version"])["changes"]
        self.assertEqual({change["kind"] for change in changes}, {"record_changed"})
        self.assertEqual(self.store.state["data_revision"], initial_revision)

        with (
            patch.object(cost_api, "repository", self.store),
            patch.object(cost_api, "configuration_service", self.configuration_service),
            patch.object(cost_api, "reference_data_service", self.service),
        ):
            preview = cost_api.preview_reference_data_draft(draft["version"], self.request())
            comparison = cost_api.preview_reference_data_comparison(draft["version"], self.request())
            self.assertEqual(preview["config_version"], 1)
            self.assertEqual(preview["reference_version"], draft["version"])
            self.assertEqual(preview["reference_state"], "draft")
            self.assertEqual(comparison["active"]["legs"][0]["fuel_tons"], 5.4)
            self.assertEqual(comparison["draft"]["legs"][0]["fuel_tons"], 8.1)

            activated = cost_api.activate_reference_data_draft(draft["version"])
            calculated = cost_api.calculate_cost(self.request())
            restored = cost_api.rollback_reference_data(1)

        self.assertEqual(activated["version"], draft["version"])
        self.assertEqual(calculated["reference_version"], draft["version"])
        self.assertEqual(calculated["config_version"], 1)
        self.assertEqual(calculated["data_snapshot"]["revision"], initial_revision)
        self.assertEqual(restored["version"], 1)
        self.assertEqual(self.store.state["data_revision"], initial_revision)
        actions = {event["action"] for event in self.store.state["audit_log"]}
        self.assertTrue({"reference_data_draft_created", "reference_data_draft_updated", "reference_data_draft_validated", "reference_data_activated", "reference_data_rolled_back"}.issubset(actions))

    def test_schema_rejects_duplicate_blank_negative_and_non_finite_reference_values(self) -> None:
        candidate = self.service.active()["reference_data"].model_dump(mode="json")
        invalid_candidates = []

        duplicate_route = copy.deepcopy(candidate)
        duplicate_route["routes"].append(copy.deepcopy(duplicate_route["routes"][0]))
        invalid_candidates.append(duplicate_route)

        duplicate_airport = copy.deepcopy(candidate)
        duplicate_airport["airport_other_costs"].append(copy.deepcopy(duplicate_airport["airport_other_costs"][0]))
        invalid_candidates.append(duplicate_airport)

        blank_identifier = copy.deepcopy(candidate)
        blank_identifier["routes"][0]["departure"] = " "
        invalid_candidates.append(blank_identifier)

        negative_amount = copy.deepcopy(candidate)
        negative_amount["airport_other_costs"][0]["amount"] = -1
        invalid_candidates.append(negative_amount)

        non_finite = copy.deepcopy(candidate)
        non_finite["routes"][0]["distance"] = math.inf
        invalid_candidates.append(non_finite)

        draft = self.service.create_draft()
        for invalid in invalid_candidates:
            with self.assertRaises(ReferenceDataValidationError):
                self.service.update_draft(draft["version"], invalid)


if __name__ == "__main__":
    unittest.main()
