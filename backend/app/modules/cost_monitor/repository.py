from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol


class CostMonitorRepository(Protocol):
    """Узкая граница хранения модуля; реализация SQL отложена."""

    def read(self) -> dict[str, Any]: ...

    def mutate(self, operation: Callable[[dict[str, Any]], Any]) -> Any: ...

    def append_audit(self, state: dict[str, Any], action: str, detail: str) -> None: ...

    def mark_calculation_data_changed(self, state: dict[str, Any]) -> int: ...
