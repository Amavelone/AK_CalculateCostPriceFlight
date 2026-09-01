from __future__ import annotations

from typing import Any, Protocol

from ..repository import CostMonitorRepository


class ConfigurationRepository(Protocol):
    """Capability-oriented граница хранения для жизненного цикла Configuration."""

    def read_configuration_state(self) -> dict[str, Any]: ...

    def create_configuration_draft(
        self,
        base_version: int,
        configuration: dict[str, Any],
        created_at: str,
    ) -> dict[str, Any]: ...

    def update_configuration_draft(
        self,
        version: int,
        configuration: dict[str, Any],
        updated_at: str,
    ) -> dict[str, Any]: ...

    def delete_configuration_draft(self, version: int) -> None: ...

    def mark_configuration_draft_validated(self, version: int, validated_at: str) -> dict[str, Any]: ...

    def activate_configuration_draft(
        self,
        version: int,
        configuration: dict[str, Any],
        activated_at: str,
    ) -> dict[str, Any]: ...

    def rollback_configuration_version(self, version: int, activated_at: str) -> dict[str, Any]: ...


class JsonConfigurationRepository:
    """Сопоставляет lifecycle-capabilities текущему атомарному адаптеру JsonStore."""

    def __init__(self, store: CostMonitorRepository) -> None:
        self._store = store

    def read_configuration_state(self) -> dict[str, Any]:
        state = self._store.read()
        return {
            "configuration_versions": state["configuration_versions"],
            "configuration_drafts": state["configuration_drafts"],
            "active_configuration_version": state["active_configuration_version"],
            "default_configuration_version": state["default_configuration_version"],
            "next_configuration_version": state["next_configuration_version"],
        }

    def create_configuration_draft(
        self,
        base_version: int,
        configuration: dict[str, Any],
        created_at: str,
    ) -> dict[str, Any]:
        def operation(state: dict[str, Any]) -> dict[str, Any]:
            version = int(state["next_configuration_version"])
            state["next_configuration_version"] = version + 1
            draft = {
                "version": version,
                "state": "draft",
                "base_version": base_version,
                "created_at": created_at,
                "updated_at": created_at,
                "validation_status": "valid",
                "configuration": configuration,
            }
            state["configuration_drafts"][str(version)] = draft
            self._store.append_audit(state, "configuration_draft_created", f"v{version} from v{base_version}")
            return draft

        return self._store.mutate(operation)

    def update_configuration_draft(
        self,
        version: int,
        configuration: dict[str, Any],
        updated_at: str,
    ) -> dict[str, Any]:
        def operation(state: dict[str, Any]) -> dict[str, Any]:
            draft = state["configuration_drafts"].get(str(version))
            if draft is None:
                raise KeyError(version)
            draft["configuration"] = configuration
            draft["updated_at"] = updated_at
            draft["validation_status"] = "valid"
            self._store.append_audit(state, "configuration_draft_updated", f"v{version}")
            return draft

        return self._store.mutate(operation)

    def delete_configuration_draft(self, version: int) -> None:
        def operation(state: dict[str, Any]) -> None:
            if str(version) not in state["configuration_drafts"]:
                raise KeyError(version)
            del state["configuration_drafts"][str(version)]
            self._store.append_audit(state, "configuration_draft_deleted", f"v{version}")

        self._store.mutate(operation)

    def mark_configuration_draft_validated(self, version: int, validated_at: str) -> dict[str, Any]:
        def operation(state: dict[str, Any]) -> dict[str, Any]:
            draft = state["configuration_drafts"].get(str(version))
            if draft is None:
                raise KeyError(version)
            draft["validation_status"] = "valid"
            draft["validated_at"] = validated_at
            self._store.append_audit(state, "configuration_draft_validated", f"v{version}")
            return draft

        return self._store.mutate(operation)

    def activate_configuration_draft(
        self,
        version: int,
        configuration: dict[str, Any],
        activated_at: str,
    ) -> dict[str, Any]:
        def operation(state: dict[str, Any]) -> dict[str, Any]:
            draft = state["configuration_drafts"].get(str(version))
            if draft is None:
                raise KeyError(version)
            for item in state["configuration_versions"]:
                item["state"] = "inactive"
            activated = {
                "version": version,
                "state": "active",
                "created_at": draft["created_at"],
                "activated_at": activated_at,
                "validation_status": "valid",
                "configuration": configuration,
            }
            state["configuration_versions"].append(activated)
            del state["configuration_drafts"][str(version)]
            state["active_configuration_version"] = version
            self._store.append_audit(state, "configuration_activated", f"v{version}")
            return activated

        return self._store.mutate(operation)

    def rollback_configuration_version(self, version: int, activated_at: str) -> dict[str, Any]:
        def operation(state: dict[str, Any]) -> dict[str, Any]:
            target = next((item for item in state["configuration_versions"] if item["version"] == version), None)
            if target is None:
                raise KeyError(version)
            for item in state["configuration_versions"]:
                item["state"] = "active" if item["version"] == version else "inactive"
            target["activated_at"] = activated_at
            state["active_configuration_version"] = version
            self._store.append_audit(state, "configuration_rolled_back", f"v{version}")
            return target

        return self._store.mutate(operation)


__all__ = ["ConfigurationRepository", "JsonConfigurationRepository"]
