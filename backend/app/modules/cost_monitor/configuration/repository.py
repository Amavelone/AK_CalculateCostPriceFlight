from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol


class ConfigurationRepository(Protocol):
    """Узкая persistence boundary для lifecycle configuration."""

    def read(self) -> dict[str, Any]: ...

    def mutate(self, operation: Callable[[dict[str, Any]], Any]) -> Any: ...

    def append_audit(self, state: dict[str, Any], action: str, detail: str) -> None: ...


class JsonConfigurationRepository:
    """Адаптер существующего JsonStore без знания calculation semantics."""

    def __init__(self, store: ConfigurationRepository) -> None:
        self._store = store

    def read(self) -> dict[str, Any]:
        return self._store.read()

    def mutate(self, operation: Callable[[dict[str, Any]], Any]) -> Any:
        return self._store.mutate(operation)

    def append_audit(self, state: dict[str, Any], action: str, detail: str) -> None:
        self._store.append_audit(state, action, detail)
