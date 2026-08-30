from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from ..catalog import normalize_key, normalize_text


def as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (float, int)):
        return float(value)
    cleaned = str(value).strip().replace(" ", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def as_hours(value: Any) -> float:
    if isinstance(value, time):
        # ИШР!P считает HOUR(E) + MINUTE(E) / 60 и намеренно игнорирует
        # секунды, даже если они присутствуют в сохранённом времени Excel.
        return value.hour + value.minute / 60
    if isinstance(value, datetime):
        return value.hour + value.minute / 60
    number = as_float(value)
    if number is None:
        return 0.0
    return number * 24 if 0 <= number <= 1 else number


def date_rank(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return normalize_text(value)


def normalize_for_json(value: Any) -> Any:
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    return value


def header_index(header: tuple[Any, ...]) -> dict[str, int]:
    return {normalize_key(value): index for index, value in enumerate(header) if normalize_text(value)}


def value_by_key(row: tuple[Any, ...], index: dict[str, int], key: str) -> Any:
    position = index.get(normalize_key(key))
    return row[position] if position is not None and position < len(row) else None
