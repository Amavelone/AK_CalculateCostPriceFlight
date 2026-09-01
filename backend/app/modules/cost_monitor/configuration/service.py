from __future__ import annotations

import copy
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from .defaults import BASELINE_CALCULATION_OVERRIDES, BASELINE_CONFIGURATION
from .presentation import PARAMETER_BY_ID, apply_business_update, business_view, describe_change, metadata
from .repository import ConfigurationRepository
from .schema import CostMonitorConfiguration
from .validation import validate_configuration


class ConfigurationError(Exception):
    """Базовая ошибка lifecycle configuration."""


class ConfigurationNotFoundError(ConfigurationError):
    """Запрошенная версия или draft отсутствует."""


class ConfigurationConflictError(ConfigurationError):
    """Операция нарушает lifecycle configuration."""


class ConfigurationValidationError(ConfigurationError):
    """Кандидат не удовлетворяет code-owned schema и ограничениям."""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def ensure_configuration_state(state: dict[str, Any], now: str | None = None) -> bool:
    """Мигрирует legacy JSON state к единственному immutable baseline v1."""

    required = {
        "configuration_versions",
        "configuration_drafts",
        "active_configuration_version",
        "next_configuration_version",
    }
    if required.issubset(state):
        changed = False
        default_version = state.get("default_configuration_version")
        if default_version is None:
            # v1 was released with version 1 as the approved baseline. Marking
            # the record is metadata-only: the historic payload is never reset.
            baseline = next((item for item in state["configuration_versions"] if item["version"] == 1), None)
            if baseline is None:
                raise ConfigurationConflictError("Не найдена release Default Configuration v1")
            baseline["is_default"] = True
            state["default_configuration_version"] = 1
            changed = True
        else:
            baseline = next((item for item in state["configuration_versions"] if item["version"] == default_version), None)
            if baseline is None:
                raise ConfigurationConflictError("Default Configuration указывает на отсутствующую версию")
            if not baseline.get("is_default"):
                baseline["is_default"] = True
                changed = True
        return changed
    created_at = now or state.get("created_at") or _now()
    state["configuration_versions"] = [
        {
            "version": 1,
            "state": "active",
            "created_at": created_at,
            "activated_at": created_at,
            "configuration": BASELINE_CONFIGURATION.model_dump(mode="json"),
            "validation_status": "valid",
            "is_default": True,
        }
    ]
    state["configuration_drafts"] = {}
    state["active_configuration_version"] = 1
    state["default_configuration_version"] = 1
    state["next_configuration_version"] = 2
    return True


def ensure_release_configuration_ownership(state: dict[str, Any]) -> bool:
    """Однократно переносит принадлежащие релизу множители и ставки сценариев в каждую config-запись."""

    marker = "release_v1_configuration_ownership_migrated"
    if state.get(marker):
        return False
    for record in [*state.get("configuration_versions", []), *state.get("configuration_drafts", {}).values()]:
        configuration = record.get("configuration")
        if not isinstance(configuration, dict):
            continue
        overrides = configuration.setdefault("overrides", {})
        multipliers = overrides.setdefault("aircraft_multipliers", {})
        for aircraft, multiplier in BASELINE_CALCULATION_OVERRIDES["aircraft_multipliers"].items():
            multipliers.setdefault(aircraft, multiplier)
        scenario_rates = overrides.setdefault("scenario_rates", {})
        for scenario, aircraft_rates in BASELINE_CALCULATION_OVERRIDES["scenario_rates"].items():
            target = scenario_rates.setdefault(scenario, {})
            for aircraft, rates in aircraft_rates.items():
                target.setdefault(aircraft, copy.deepcopy(rates))
    state[marker] = True
    return True


def _configuration_from(value: Mapping[str, Any]) -> CostMonitorConfiguration:
    try:
        return validate_configuration(value)
    except ValidationError as error:
        first = error.errors()[0]
        path = ".".join(str(part) for part in first["loc"])
        parameter = PARAMETER_BY_ID.get(path)
        if parameter:
            raise ConfigurationValidationError(
                f"{next(group['label'] for group in metadata()['groups'] if group['id'] == parameter['group'])} → "
                f"{parameter['label']}: {first['msg']} ({path})"
            ) from error
        raise ConfigurationValidationError(str(error)) from error
    except ValueError as error:
        raise ConfigurationValidationError(str(error)) from error


def _find_version(state: Mapping[str, Any], version: int) -> dict[str, Any]:
    for item in state["configuration_versions"]:
        if item["version"] == version:
            return item
    raise ConfigurationNotFoundError(f"Версия configuration {version} не найдена")


def _find_draft(state: Mapping[str, Any], version: int) -> dict[str, Any]:
    draft = state["configuration_drafts"].get(str(version))
    if draft is None:
        raise ConfigurationNotFoundError(f"Draft configuration {version} не найден")
    return draft


def _summary(record: Mapping[str, Any]) -> dict[str, Any]:
    summary = {
        "version": record["version"],
        "state": record["state"],
        "created_at": record["created_at"],
        "activated_at": record.get("activated_at"),
        "validation_status": record["validation_status"],
        "is_default": bool(record.get("is_default", False)),
    }
    if "updated_at" in record:
        summary["updated_at"] = record["updated_at"]
    if "base_version" in record:
        summary["base_version"] = record["base_version"]
    return summary


def _change(path: str, before: Any, after: Any, kind: str | None = None) -> dict[str, Any]:
    if kind is None:
        kind = "override_changed" if path.startswith("overrides.") else "parameter_changed"
    labels = {
        "operation_added": "Добавлена operation part",
        "operation_removed": "Удалена operation part",
        "operation_reordered": "Изменён порядок operation parts",
        "operation_changed": "Изменена operation part",
        "override_changed": "Изменён admin override",
        "parameter_changed": "Изменён parameter",
    }
    return {"path": path, "before": before, "after": after, "kind": kind, "summary": labels[kind]}


def _diff(left: Any, right: Any, path: str = "") -> list[dict[str, Any]]:
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        changes: list[dict[str, Any]] = []
        for key in sorted(set(left) | set(right)):
            next_path = f"{path}.{key}" if path else str(key)
            if key not in left or key not in right:
                changes.append(_change(next_path, left.get(key), right.get(key)))
            else:
                changes.extend(_diff(left[key], right[key], next_path))
        return changes
    if path.endswith(".parts") and isinstance(left, list) and isinstance(right, list):
        left_by_id = {item["id"]: item for item in left}
        right_by_id = {item["id"]: item for item in right}
        changes = []
        for part_id in sorted(set(right_by_id) - set(left_by_id)):
            changes.append(_change(f"{path}[{part_id}]", None, right_by_id[part_id], "operation_added"))
        for part_id in sorted(set(left_by_id) - set(right_by_id)):
            changes.append(_change(f"{path}[{part_id}]", left_by_id[part_id], None, "operation_removed"))
        left_order = [item["id"] for item in left]
        right_order = [item["id"] for item in right]
        if set(left_order) == set(right_order) and left_order != right_order:
            changes.append(_change(f"{path}.order", left_order, right_order, "operation_reordered"))
        for part_id in sorted(set(left_by_id) & set(right_by_id)):
            if left_by_id[part_id] != right_by_id[part_id]:
                changes.append(
                    _change(
                        f"{path}[{part_id}]",
                        left_by_id[part_id],
                        right_by_id[part_id],
                        "operation_changed",
                    )
                )
        return changes
    return [] if left == right else [_change(path, left, right)]


class ConfigurationService:
    """Управляет versioned runtime configuration в пределах Cost Monitor."""

    def __init__(self, repository: ConfigurationRepository) -> None:
        self._repository = repository

    def active(self) -> dict[str, Any]:
        state = self._repository.read_configuration_state()
        version = _find_version(state, int(state["active_configuration_version"]))
        return {**_summary(version), "configuration": _configuration_from(version["configuration"])}

    def default(self) -> dict[str, Any]:
        state = self._repository.read_configuration_state()
        version = _find_version(state, int(state["default_configuration_version"]))
        if not version.get("is_default"):
            raise ConfigurationConflictError("Default Configuration не помечена immutable")
        return {**_summary(version), "configuration": _configuration_from(version["configuration"])}

    def list_versions(self) -> list[dict[str, Any]]:
        state = self._repository.read_configuration_state()
        return [_summary(item) for item in sorted(state["configuration_versions"], key=lambda item: item["version"])]

    def create_draft(self, base: str = "active") -> dict[str, Any]:
        state = self._repository.read_configuration_state()
        if base == "active":
            source = _find_version(state, int(state["active_configuration_version"]))
        elif base == "default":
            source = _find_version(state, int(state["default_configuration_version"]))
        else:
            raise ConfigurationValidationError("Основа draft должна быть Default или Current Active.")
        configuration = _configuration_from(source["configuration"]).model_dump(mode="json")
        return self._repository.create_configuration_draft(source["version"], configuration, _now())

    def update_draft(self, version: int, candidate: Mapping[str, Any]) -> dict[str, Any]:
        configuration = _configuration_from(candidate)
        try:
            return self._repository.update_configuration_draft(
                version,
                configuration.model_dump(mode="json"),
                _now(),
            )
        except KeyError as error:
            raise ConfigurationNotFoundError(f"Draft configuration {version} не найден") from error

    def business_draft(self, version: int) -> dict[str, Any]:
        return {"draft": self.draft(version), "business": business_view(self.draft_configuration(version))}

    def update_business_draft(self, version: int, candidate: Mapping[str, Any]) -> dict[str, Any]:
        current = self.draft_configuration(version)
        try:
            translated = apply_business_update(current, candidate)
        except ValueError as error:
            raise ConfigurationValidationError(str(error)) from error
        return self.update_draft(version, translated)

    def delete_draft(self, version: int) -> None:
        try:
            self._repository.delete_configuration_draft(version)
        except KeyError as error:
            raise ConfigurationNotFoundError(f"Draft configuration {version} не найден") from error

    def validate_draft(self, version: int) -> dict[str, Any]:
        state = self._repository.read_configuration_state()
        _configuration_from(_find_draft(state, version)["configuration"])
        try:
            return self._repository.mark_configuration_draft_validated(version, _now())
        except KeyError as error:
            raise ConfigurationNotFoundError(f"Draft configuration {version} не найден") from error

    def draft_configuration(self, version: int) -> CostMonitorConfiguration:
        state = self._repository.read_configuration_state()
        return _configuration_from(_find_draft(state, version)["configuration"])

    def draft(self, version: int) -> dict[str, Any]:
        state = self._repository.read_configuration_state()
        draft = dict(_find_draft(state, version))
        draft["configuration"] = _configuration_from(draft["configuration"]).model_dump(mode="json")
        return draft

    def compare(self, left_version: int, right_version: int) -> dict[str, Any]:
        state = self._repository.read_configuration_state()

        def resolve(version: int) -> dict[str, Any]:
            try:
                return _find_version(state, version)
            except ConfigurationNotFoundError:
                return _find_draft(state, version)

        left = resolve(left_version)
        right = resolve(right_version)
        left_configuration = _configuration_from(left["configuration"]).model_dump(mode="json")
        right_configuration = _configuration_from(right["configuration"]).model_dump(mode="json")
        return {
            "left": _summary(left),
            "right": _summary(right),
            "changes": [describe_change(change) for change in _diff(left_configuration, right_configuration)],
        }

    def presentation_metadata(self) -> dict[str, Any]:
        return metadata()

    def export_snapshot(self, version: int) -> dict[str, Any]:
        state = self._repository.read_configuration_state()
        try:
            record = _find_version(state, version)
        except ConfigurationNotFoundError:
            record = _find_draft(state, version)
        return {
            "export_schema_version": "1.0",
            "configuration_identity": _summary(record),
            "configuration": _configuration_from(record["configuration"]).model_dump(mode="json"),
            "allowed_operation_configuration": metadata()["advanced"],
        }

    def activate(self, version: int) -> dict[str, Any]:
        state = self._repository.read_configuration_state()
        configuration = _configuration_from(_find_draft(state, version)["configuration"])
        try:
            return self._repository.activate_configuration_draft(
                version,
                configuration.model_dump(mode="json"),
                _now(),
            )
        except KeyError as error:
            raise ConfigurationNotFoundError(f"Draft configuration {version} не найден") from error

    def rollback(self, version: int) -> dict[str, Any]:
        state = self._repository.read_configuration_state()
        target = _find_version(state, version)
        _configuration_from(target["configuration"])
        if target["version"] == state["active_configuration_version"]:
            raise ConfigurationConflictError(f"Версия configuration {version} уже активна")
        try:
            restored = self._repository.rollback_configuration_version(version, _now())
            return {
                **restored,
                "configuration": _configuration_from(restored["configuration"]).model_dump(mode="json"),
            }
        except KeyError as error:
            raise ConfigurationNotFoundError(f"Версия configuration {version} не найдена") from error
