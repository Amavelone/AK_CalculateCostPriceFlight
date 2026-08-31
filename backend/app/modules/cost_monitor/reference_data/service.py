from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from .defaults import BASELINE_REFERENCE_DATA
from .repository import ReferenceDataRepository
from .schema import CostMonitorReferenceData


class ReferenceDataError(Exception):
    """Base lifecycle error for Cost Monitor Reference Data."""


class ReferenceDataNotFoundError(ReferenceDataError):
    """Requested version or draft does not exist."""


class ReferenceDataConflictError(ReferenceDataError):
    """Requested lifecycle transition is not valid for its current state."""


class ReferenceDataValidationError(ReferenceDataError):
    """Candidate cannot become a Cost Monitor Reference Data version."""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _legacy_reference_payload(state: Mapping[str, Any]) -> dict[str, Any]:
    routes = []
    for item in state.get("routes", []):
        routes.append(
            {
                "departure": item.get("departure") or str(item.get("key", "")).split("-", maxsplit=1)[0],
                "arrival": item.get("arrival") or str(item.get("key", "")).split("-", maxsplit=1)[-1],
                "distance": item.get("distance", 0),
                "flight_time": item.get("flight_time", 0),
                "source_row": item.get("source_row"),
            }
        )
    other_costs = [
        {"airport": airport, "amount": amount}
        for airport, amount in state.get("other_costs", {}).items()
    ]
    baseline = BASELINE_REFERENCE_DATA.model_dump(mode="json")
    return {
        "schema_version": "1.0",
        "routes": routes or baseline["routes"],
        "airport_other_costs": other_costs or baseline["airport_other_costs"],
    }


def ensure_reference_data_state(state: dict[str, Any], now: str | None = None) -> bool:
    """Migrate the former unversioned routes/other-costs fields into active v1."""

    required = {
        "reference_data_versions",
        "reference_data_drafts",
        "active_reference_data_version",
        "next_reference_data_version",
    }
    if required.issubset(state):
        return False
    created_at = now or state.get("created_at") or _now()
    payload = _validate_reference_data(_legacy_reference_payload(state)).model_dump(mode="json")
    state["reference_data_versions"] = [
        {
            "version": 1,
            "state": "active",
            "created_at": created_at,
            "activated_at": created_at,
            "validation_status": "valid",
            "reference_data": payload,
        }
    ]
    state["reference_data_drafts"] = {}
    state["active_reference_data_version"] = 1
    state["next_reference_data_version"] = 2
    state.pop("routes", None)
    state.pop("other_costs", None)
    return True


def _validate_reference_data(value: Mapping[str, Any]) -> CostMonitorReferenceData:
    try:
        return CostMonitorReferenceData.model_validate(value)
    except (ValidationError, ValueError) as error:
        raise ReferenceDataValidationError(str(error)) from error


def _find_version(state: Mapping[str, Any], version: int) -> dict[str, Any]:
    for item in state["reference_data_versions"]:
        if item["version"] == version:
            return item
    raise ReferenceDataNotFoundError(f"Reference Data version {version} not found")


def _find_draft(state: Mapping[str, Any], version: int) -> dict[str, Any]:
    draft = state["reference_data_drafts"].get(str(version))
    if draft is None:
        raise ReferenceDataNotFoundError(f"Reference Data draft {version} not found")
    return draft


def _summary(record: Mapping[str, Any]) -> dict[str, Any]:
    result = {
        "version": record["version"],
        "state": record["state"],
        "created_at": record["created_at"],
        "activated_at": record.get("activated_at"),
        "validation_status": record["validation_status"],
    }
    if "updated_at" in record:
        result["updated_at"] = record["updated_at"]
    if "base_version" in record:
        result["base_version"] = record["base_version"]
    return result


def _records_by_key(reference_data: CostMonitorReferenceData) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    routes = {route.key: route.model_dump(mode="json") for route in reference_data.routes}
    other_costs = {item.airport: item.model_dump(mode="json") for item in reference_data.airport_other_costs}
    return routes, other_costs


def _diff(left: CostMonitorReferenceData, right: CostMonitorReferenceData) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    left_routes, left_other = _records_by_key(left)
    right_routes, right_other = _records_by_key(right)
    for name, before_records, after_records in (
        ("routes", left_routes, right_routes),
        ("airport_other_costs", left_other, right_other),
    ):
        for key in sorted(set(before_records) | set(after_records)):
            before = before_records.get(key)
            after = after_records.get(key)
            if before == after:
                continue
            kind = "record_added" if before is None else "record_removed" if after is None else "record_changed"
            changes.append(
                {
                    "path": f"{name}.{key}",
                    "before": before,
                    "after": after,
                    "kind": kind,
                    "summary": {
                        "record_added": "Reference record added",
                        "record_removed": "Reference record removed",
                        "record_changed": "Reference record changed",
                    }[kind],
                }
            )
    return changes


class ReferenceDataService:
    """Owns immutable versions and drafts for Cost Monitor routes and airport costs."""

    def __init__(self, repository: ReferenceDataRepository) -> None:
        self._repository = repository

    def active(self) -> dict[str, Any]:
        state = self._repository.read_reference_state()
        version = _find_version(state, int(state["active_reference_data_version"]))
        return {**_summary(version), "reference_data": _validate_reference_data(version["reference_data"])}

    def list_versions(self) -> list[dict[str, Any]]:
        state = self._repository.read_reference_state()
        return [_summary(item) for item in sorted(state["reference_data_versions"], key=lambda item: item["version"])]

    def create_draft(self) -> dict[str, Any]:
        state = self._repository.read_reference_state()
        active = _find_version(state, int(state["active_reference_data_version"]))
        reference_data = _validate_reference_data(active["reference_data"]).model_dump(mode="json")
        return self._repository.create_reference_draft(active["version"], reference_data, _now())

    def update_draft(self, version: int, candidate: Mapping[str, Any]) -> dict[str, Any]:
        reference_data = _validate_reference_data(candidate)
        try:
            return self._repository.update_reference_draft(version, reference_data.model_dump(mode="json"), _now())
        except KeyError as error:
            raise ReferenceDataNotFoundError(f"Reference Data draft {version} not found") from error

    def validate_draft(self, version: int) -> dict[str, Any]:
        state = self._repository.read_reference_state()
        _validate_reference_data(_find_draft(state, version)["reference_data"])
        try:
            return self._repository.validate_reference_draft(version, _now())
        except KeyError as error:
            raise ReferenceDataNotFoundError(f"Reference Data draft {version} not found") from error

    def draft_data(self, version: int) -> CostMonitorReferenceData:
        state = self._repository.read_reference_state()
        return _validate_reference_data(_find_draft(state, version)["reference_data"])

    def draft(self, version: int) -> dict[str, Any]:
        state = self._repository.read_reference_state()
        draft = dict(_find_draft(state, version))
        draft["reference_data"] = _validate_reference_data(draft["reference_data"]).model_dump(mode="json")
        return draft

    def compare(self, left_version: int, right_version: int) -> dict[str, Any]:
        state = self._repository.read_reference_state()

        def resolve(version: int) -> dict[str, Any]:
            try:
                return _find_version(state, version)
            except ReferenceDataNotFoundError:
                return _find_draft(state, version)

        left = resolve(left_version)
        right = resolve(right_version)
        return {
            "left": _summary(left),
            "right": _summary(right),
            "changes": _diff(
                _validate_reference_data(left["reference_data"]),
                _validate_reference_data(right["reference_data"]),
            ),
        }

    def activate(self, version: int) -> dict[str, Any]:
        state = self._repository.read_reference_state()
        reference_data = _validate_reference_data(_find_draft(state, version)["reference_data"])
        try:
            return self._repository.activate_reference_draft(version, reference_data.model_dump(mode="json"), _now())
        except KeyError as error:
            raise ReferenceDataNotFoundError(f"Reference Data draft {version} not found") from error

    def rollback(self, version: int) -> dict[str, Any]:
        state = self._repository.read_reference_state()
        target = _find_version(state, version)
        _validate_reference_data(target["reference_data"])
        if target["version"] == state["active_reference_data_version"]:
            raise ReferenceDataConflictError(f"Reference Data version {version} is already active")
        try:
            restored = self._repository.rollback_reference_version(version, _now())
            return {**restored, "reference_data": _validate_reference_data(restored["reference_data"]).model_dump(mode="json")}
        except KeyError as error:
            raise ReferenceDataNotFoundError(f"Reference Data version {version} not found") from error


__all__ = [
    "ReferenceDataConflictError",
    "ReferenceDataError",
    "ReferenceDataNotFoundError",
    "ReferenceDataService",
    "ReferenceDataValidationError",
    "ensure_reference_data_state",
]
