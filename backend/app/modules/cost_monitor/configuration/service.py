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


def _diff(left: Any, right: Any, path: str = "") -> list[dict[str, Any]]:
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        changes: list[dict[str, Any]] = []
        for key in sorted(set(left) | set(right)):
            next_path = f"{path}.{key}" if path else str(key)
            if key not in left or key not in right:
                changes.append({"path": next_path, "before": left.get(key), "after": right.get(key)})
            else:
                changes.extend(_diff(left[key], right[key], next_path))
        return changes
    return [] if left == right else [{"path": path, "before": left, "after": right}]


class ConfigurationService:
    """Управляет versioned runtime configuration в пределах Cost Monitor."""

    def __init__(self, repository: ConfigurationRepository) -> None:
        self._repository = repository

    def active(self) -> dict[str, Any]:
        state = self._repository.read()
        version = _find_version(state, int(state["active_configuration_version"]))
        return {**_summary(version), "configuration": _configuration_from(version["configuration"])}

    def list_versions(self) -> list[dict[str, Any]]:
        state = self._repository.read()
        return [_summary(item) for item in sorted(state["configuration_versions"], key=lambda item: item["version"])]

    def create_draft(self) -> dict[str, Any]:
        def operation(state: dict[str, Any]) -> dict[str, Any]:
            active = _find_version(state, int(state["active_configuration_version"]))
            version = int(state["next_configuration_version"])
            state["next_configuration_version"] = version + 1
            now = _now()
            draft = {
                "version": version,
                "state": "draft",
                "base_version": active["version"],
                "created_at": now,
                "updated_at": now,
                "validation_status": "valid",
                "configuration": _configuration_from(active["configuration"]).model_dump(mode="json"),
            }
            state["configuration_drafts"][str(version)] = draft
            self._repository.append_audit(state, "configuration_draft_created", f"v{version} from v{active['version']}")
            return draft

        return self._repository.mutate(operation)

    def update_draft(self, version: int, candidate: Mapping[str, Any]) -> dict[str, Any]:
        configuration = _configuration_from(candidate)

        def operation(state: dict[str, Any]) -> dict[str, Any]:
            draft = _find_draft(state, version)
            draft["configuration"] = configuration.model_dump(mode="json")
            draft["updated_at"] = _now()
            draft["validation_status"] = "valid"
            self._repository.append_audit(state, "configuration_draft_updated", f"v{version}")
            return draft

        return self._repository.mutate(operation)

    def validate_draft(self, version: int) -> dict[str, Any]:
        def operation(state: dict[str, Any]) -> dict[str, Any]:
            draft = _find_draft(state, version)
            _configuration_from(draft["configuration"])
            draft["validation_status"] = "valid"
            draft["validated_at"] = _now()
            self._repository.append_audit(state, "configuration_draft_validated", f"v{version}")
            return draft

        return self._repository.mutate(operation)

    def draft_configuration(self, version: int) -> CostMonitorConfiguration:
        state = self._repository.read()
        return _configuration_from(_find_draft(state, version)["configuration"])

    def compare(self, left_version: int, right_version: int) -> dict[str, Any]:
        state = self._repository.read()

        def resolve(version: int) -> dict[str, Any]:
            try:
                return _find_version(state, version)
            except ConfigurationNotFoundError:
                return _find_draft(state, version)

        left = resolve(left_version)
        right = resolve(right_version)
        return {
            "left": _summary(left),
            "right": _summary(right),
            "changes": _diff(left["configuration"], right["configuration"]),
        }

    def activate(self, version: int) -> dict[str, Any]:
        def operation(state: dict[str, Any]) -> dict[str, Any]:
            draft = _find_draft(state, version)
            configuration = _configuration_from(draft["configuration"])
            now = _now()
            for item in state["configuration_versions"]:
                item["state"] = "inactive"
            activated = {
                "version": version,
                "state": "active",
                "created_at": draft["created_at"],
                "activated_at": now,
                "validation_status": "valid",
                "configuration": configuration.model_dump(mode="json"),
            }
            state["configuration_versions"].append(activated)
            del state["configuration_drafts"][str(version)]
            state["active_configuration_version"] = version
            self._repository.append_audit(state, "configuration_activated", f"v{version}")
            return activated

        return self._repository.mutate(operation)

    def rollback(self, version: int) -> dict[str, Any]:
        def operation(state: dict[str, Any]) -> dict[str, Any]:
            target = _find_version(state, version)
            _configuration_from(target["configuration"])
            if target["version"] == state["active_configuration_version"]:
                raise ConfigurationConflictError(f"Версия configuration {version} уже активна")
            for item in state["configuration_versions"]:
                item["state"] = "active" if item["version"] == version else "inactive"
            target["activated_at"] = _now()
            state["active_configuration_version"] = version
            self._repository.append_audit(state, "configuration_rolled_back", f"v{version}")
            return target

        return self._repository.mutate(operation)
