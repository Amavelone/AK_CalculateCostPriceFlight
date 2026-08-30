from __future__ import annotations

from typing import Any


def normalize_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def normalize_key(value: Any) -> str:
    return normalize_text(value).upper().replace("Ё", "Е")


def tariffs_for_view(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Объединяет импортированные и ручные тарифы в порядке первого совпадения Excel.

    Импортированные строки идут первыми, а совпадающие ручные значения
    сохраняются и помечаются как конфликтные, но не переопределяют расчёт.
    """

    imported = [dict(item, conflict=False) for item in state.get("imported_tariffs", [])]
    imported_keys = {f"{item['airport']}-{item['service']}" for item in imported}
    manual = [
        dict(item, conflict=f"{item['airport']}-{item['service']}" in imported_keys)
        for item in state.get("manual_tariffs", [])
    ]
    return imported + manual
