from __future__ import annotations

from typing import Any, Protocol

from ..repository import CostMonitorRepository


class ReferenceDataRepository(Protocol):
    """Persistence operations required by the Reference Data lifecycle."""

    def read_reference_state(self) -> dict[str, Any]: ...

    def create_reference_draft(self, base_version: int, reference_data: dict[str, Any], created_at: str) -> dict[str, Any]: ...

    def update_reference_draft(self, version: int, reference_data: dict[str, Any], updated_at: str) -> dict[str, Any]: ...

    def validate_reference_draft(self, version: int, validated_at: str) -> dict[str, Any]: ...

    def activate_reference_draft(self, version: int, reference_data: dict[str, Any], activated_at: str) -> dict[str, Any]: ...

    def rollback_reference_version(self, version: int, activated_at: str) -> dict[str, Any]: ...


class JsonReferenceDataRepository:
    """Maps reference-data lifecycle operations to the atomic JsonStore adapter."""

    def __init__(self, store: CostMonitorRepository) -> None:
        self._store = store

    def read_reference_state(self) -> dict[str, Any]:
        state = self._store.read()
        return {
            "reference_data_versions": state["reference_data_versions"],
            "reference_data_drafts": state["reference_data_drafts"],
            "active_reference_data_version": state["active_reference_data_version"],
            "next_reference_data_version": state["next_reference_data_version"],
        }

    def create_reference_draft(self, base_version: int, reference_data: dict[str, Any], created_at: str) -> dict[str, Any]:
        def operation(state: dict[str, Any]) -> dict[str, Any]:
            version = int(state["next_reference_data_version"])
            state["next_reference_data_version"] = version + 1
            draft = {
                "version": version,
                "state": "draft",
                "base_version": base_version,
                "created_at": created_at,
                "updated_at": created_at,
                "validation_status": "valid",
                "reference_data": reference_data,
            }
            state["reference_data_drafts"][str(version)] = draft
            self._store.append_audit(state, "reference_data_draft_created", f"v{version} from v{base_version}")
            return draft

        return self._store.mutate(operation)

    def update_reference_draft(self, version: int, reference_data: dict[str, Any], updated_at: str) -> dict[str, Any]:
        def operation(state: dict[str, Any]) -> dict[str, Any]:
            draft = state["reference_data_drafts"].get(str(version))
            if draft is None:
                raise KeyError(version)
            draft["reference_data"] = reference_data
            draft["updated_at"] = updated_at
            draft["validation_status"] = "valid"
            self._store.append_audit(state, "reference_data_draft_updated", f"v{version}")
            return draft

        return self._store.mutate(operation)

    def validate_reference_draft(self, version: int, validated_at: str) -> dict[str, Any]:
        def operation(state: dict[str, Any]) -> dict[str, Any]:
            draft = state["reference_data_drafts"].get(str(version))
            if draft is None:
                raise KeyError(version)
            draft["validation_status"] = "valid"
            draft["validated_at"] = validated_at
            self._store.append_audit(state, "reference_data_draft_validated", f"v{version}")
            return draft

        return self._store.mutate(operation)

    def activate_reference_draft(self, version: int, reference_data: dict[str, Any], activated_at: str) -> dict[str, Any]:
        def operation(state: dict[str, Any]) -> dict[str, Any]:
            draft = state["reference_data_drafts"].get(str(version))
            if draft is None:
                raise KeyError(version)
            for item in state["reference_data_versions"]:
                item["state"] = "inactive"
            active = {
                "version": version,
                "state": "active",
                "created_at": draft["created_at"],
                "activated_at": activated_at,
                "validation_status": "valid",
                "reference_data": reference_data,
            }
            state["reference_data_versions"].append(active)
            del state["reference_data_drafts"][str(version)]
            state["active_reference_data_version"] = version
            self._store.append_audit(state, "reference_data_activated", f"v{version}")
            return active

        return self._store.mutate(operation)

    def rollback_reference_version(self, version: int, activated_at: str) -> dict[str, Any]:
        def operation(state: dict[str, Any]) -> dict[str, Any]:
            target = next((item for item in state["reference_data_versions"] if item["version"] == version), None)
            if target is None:
                raise KeyError(version)
            for item in state["reference_data_versions"]:
                item["state"] = "active" if item["version"] == version else "inactive"
            target["activated_at"] = activated_at
            state["active_reference_data_version"] = version
            self._store.append_audit(state, "reference_data_rolled_back", f"v{version}")
            return target

        return self._store.mutate(operation)


__all__ = ["JsonReferenceDataRepository", "ReferenceDataRepository"]
