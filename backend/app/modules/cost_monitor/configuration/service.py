from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from .defaults import BASELINE_CONFIGURATION
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
        return False
    created_at = now or state.get("created_at") or _now()
    state["configuration_versions"] = [
        {
            "version": 1,
            "state": "active",
            "created_at": created_at,
            "activated_at": created_at,
            "configuration": BASELINE_CONFIGURATION.model_dump(mode="json"),
            "validation_status": "valid",
        }
    ]
    state["configuration_drafts"] = {}
    state["active_configuration_version"] = 1
    state["next_configuration_version"] = 2
    return True


def _configuration_from(value: Mapping[str, Any]) -> CostMonitorConfiguration:
    try:
        return validate_configuration(value)
    except (ValidationError, ValueError) as error:
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

    def list_versions(self) -> list[dict[str, Any]]:
        state = self._repository.read_configuration_state()
        return [_summary(item) for item in sorted(state["configuration_versions"], key=lambda item: item["version"])]

    def create_draft(self) -> dict[str, Any]:
        state = self._repository.read_configuration_state()
        active = _find_version(state, int(state["active_configuration_version"]))
        configuration = _configuration_from(active["configuration"]).model_dump(mode="json")
        return self._repository.create_configuration_draft(active["version"], configuration, _now())

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
            "changes": _diff(left_configuration, right_configuration),
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
