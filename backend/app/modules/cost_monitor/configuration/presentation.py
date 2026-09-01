"""Business-facing metadata layered over the bounded configuration schema.

The calculator owns the meaning of values; this module only gives supported
configuration fields a stable, human-readable administrative representation.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

from .schema import CostMonitorConfiguration

GROUPS = (
    {"id": "main", "label": "Основные параметры", "description": "НДС и общие правила расчёта."},
    {"id": "fuel", "label": "Топливо", "description": "Расход топлива для расчёта объёма ГСМ."},
    {"id": "ground", "label": "Наземное обслуживание", "description": "Параметры объёмов услуг НО."},
    {"id": "ano", "label": "АНО", "description": "Маршрутная составляющая аэронавигационного обслуживания."},
    {"id": "catering", "label": "Бортовое питание", "description": "Базовая и пассажирская части питания."},
    {"id": "flight_hour", "label": "Лётный час / M1 / M2 / M3", "description": "Сценарии, типы ВС и ставки лётного часа."},
)


PARAMETERS: tuple[dict[str, Any], ...] = (
    {
        "id": "vat.rate",
        "label": "Ставка НДС",
        "description": "Ставка НДС для применимых внутренних плеч.",
        "group": "main",
        "unit": "%",
        "editable": True,
        "advanced": False,
        "bounds": {"min": 0, "max": 100},
        "where_used": ["НДС → итоговая стоимость плеча"],
    },
    {
        "id": "vat.airports",
        "label": "Аэропорты применения НДС",
        "description": "НДС применяется, если один из аэропортов плеча входит в список.",
        "group": "main",
        "unit": "IATA",
        "editable": True,
        "advanced": False,
        "bounds": {"min_items": 1, "max_items": 100},
        "where_used": ["НДС → правило применимости"],
    },
    {
        "id": "fuel.consumption_tons_per_hour",
        "label": "Расход топлива",
        "description": "Нормативный расход для определения объёма ГСМ по налёту.",
        "group": "fuel",
        "unit": "т/ч",
        "editable": True,
        "advanced": False,
        "bounds": {"exclusive_min": 0, "max": 100},
        "where_used": ["Топливо → объём ГСМ", "НО → керосин и заправка"],
    },
    {
        "id": "ground.split_divisor",
        "label": "Делитель услуг",
        "description": "Коэффициент распределения общих услуг наземного обслуживания.",
        "group": "ground",
        "unit": "раз",
        "editable": True,
        "advanced": False,
        "bounds": {"exclusive_min": 0, "max": 1000},
        "where_used": ["НО → телетрап", "НО → транспорт", "НО → трап", "НО → пожарная машина"],
    },
    {
        "id": "ground.stairs_units",
        "label": "Количество трапов",
        "description": "Объём услуги «ТРАП» для обычного и технического плеча.",
        "group": "ground",
        "unit": "ед.",
        "editable": True,
        "advanced": False,
        "bounds": {"min": 0, "max": 1000},
        "where_used": ["НО → трап"],
    },
    {
        "id": "ground.telebridge_minutes",
        "label": "Время телетрапа",
        "description": "Объём услуги «ТЕЛЕТРАП МИН» для обычного плеча.",
        "group": "ground",
        "unit": "мин.",
        "editable": True,
        "advanced": False,
        "bounds": {"min": 0, "max": 1440},
        "where_used": ["НО → телетрап"],
    },
    {
        "id": "ground.transport_passenger_block",
        "label": "Пассажиров на единицу транспорта",
        "description": "Размер блока пассажиров для расчёта количества транспорта.",
        "group": "ground",
        "unit": "пасс.",
        "editable": True,
        "advanced": False,
        "bounds": {"exclusive_min": 0, "max": 100000},
        "where_used": ["НО → транспорт"],
    },
    {
        "id": "ground.fire_truck_rate",
        "label": "Стоимость пожарной машины",
        "description": "Фиксированная стоимость пожарной машины при технической посадке.",
        "group": "ground",
        "unit": "₽",
        "editable": True,
        "advanced": False,
        "bounds": {"min": 0, "max": 100000000},
        "where_used": ["НО → пожарная машина (техстоп)"],
    },
    {
        "id": "ano.route_rate_per_100_km",
        "label": "Маршрутная ставка АНО",
        "description": "Ставка маршрутной части аэронавигационного обслуживания.",
        "group": "ano",
        "unit": "₽ / 100 км",
        "editable": True,
        "advanced": False,
        "bounds": {"min": 0, "max": 100000000},
        "where_used": ["АНО → маршрутная часть"],
    },
    {
        "id": "catering.base_units",
        "label": "Базовое количество комплектов",
        "description": "Количество базовых комплектов бортового питания на плечо.",
        "group": "catering",
        "unit": "ед.",
        "editable": True,
        "advanced": False,
        "bounds": {"min": 0, "max": 1000},
        "where_used": ["Бортовое питание → базовая часть"],
    },
    {
        "id": "catering.base_unit_rate",
        "label": "Стоимость базового комплекта",
        "description": "Цена одного базового комплекта бортового питания.",
        "group": "catering",
        "unit": "₽ / ед.",
        "editable": True,
        "advanced": False,
        "bounds": {"min": 0, "max": 100000000},
        "where_used": ["Бортовое питание → базовая часть"],
    },
    {
        "id": "catering.passenger_surcharge",
        "label": "Доплата за пассажира",
        "description": "Доплата на пассажира при включённой пассажирской части питания.",
        "group": "catering",
        "unit": "₽ / пассажир",
        "editable": True,
        "advanced": False,
        "bounds": {"min": 0, "max": 10000000},
        "where_used": ["Бортовое питание → доплата за пассажиров"],
    },
)

PARAMETER_BY_ID = {item["id"]: item for item in PARAMETERS}

ADVANCED_CAPABILITIES = {
    "operations": {"enabled": True, "steps": ["ano", "catering", "vat"]},
    "lookups": {"enabled": True},
    "conditions": {"enabled": True},
}


def metadata() -> dict[str, Any]:
    return {
        "groups": copy.deepcopy(list(GROUPS)),
        "parameters": copy.deepcopy(list(PARAMETERS)),
        "advanced": copy.deepcopy(ADVANCED_CAPABILITIES),
    }


def _read_path(value: Mapping[str, Any], path: str) -> Any:
    current: Any = value
    for segment in path.split("."):
        current = current[segment]
    return copy.deepcopy(current)


def _write_path(value: dict[str, Any], path: str, replacement: Any) -> None:
    current: dict[str, Any] = value
    *parents, leaf = path.split(".")
    for segment in parents:
        current = current[segment]
    current[leaf] = replacement


def business_view(configuration: CostMonitorConfiguration) -> dict[str, Any]:
    payload = configuration.model_dump(mode="json")
    return {
        "metadata": metadata(),
        "values": {item["id"]: _read_path(payload, item["id"]) for item in PARAMETERS},
        "flight_hour": {
            "aircraft_multipliers": copy.deepcopy(payload["overrides"]["aircraft_multipliers"]),
            "scenario_rates": copy.deepcopy(payload["overrides"]["scenario_rates"]),
        },
    }


def apply_business_update(configuration: CostMonitorConfiguration, candidate: Mapping[str, Any]) -> dict[str, Any]:
    """Translate only presentation-owned edits back into the typed payload.

    Operations remain untouched. This prevents Basic mode from accidentally
    becoming another generic execution-graph editor.
    """

    unknown_sections = set(candidate) - {"values", "flight_hour"}
    if unknown_sections:
        raise ValueError(f"Неподдерживаемые разделы Business Configuration: {', '.join(sorted(unknown_sections))}")
    payload = configuration.model_dump(mode="json")
    values = candidate.get("values", {})
    if not isinstance(values, Mapping):
        raise ValueError("Параметры Business Configuration должны быть объектом.")
    unknown_values = set(values) - set(PARAMETER_BY_ID)
    if unknown_values:
        raise ValueError(f"Неподдерживаемые параметры: {', '.join(sorted(unknown_values))}")
    for path, replacement in values.items():
        _write_path(payload, path, replacement)

    if "flight_hour" in candidate:
        flight_hour = candidate["flight_hour"]
        if not isinstance(flight_hour, Mapping):
            raise ValueError("Лётный час должен быть объектом.")
        unknown_flight_fields = set(flight_hour) - {"aircraft_multipliers", "scenario_rates"}
        if unknown_flight_fields:
            raise ValueError(f"Неподдерживаемые параметры лётного часа: {', '.join(sorted(unknown_flight_fields))}")
        for field in ("aircraft_multipliers", "scenario_rates"):
            if field not in flight_hour:
                continue
            replacement = flight_hour[field]
            current = payload["overrides"][field]
            if not isinstance(replacement, Mapping) or set(replacement) != set(current):
                raise ValueError("Basic mode позволяет менять значения существующих ставок, но не состав сценариев или типов ВС.")
            if field == "scenario_rates" and any(
                not isinstance(rates, Mapping) or set(rates) != set(current[scenario])
                for scenario, rates in replacement.items()
            ):
                raise ValueError("Basic mode позволяет менять значения существующей матрицы M1/M2/M3.")
            payload["overrides"][field] = copy.deepcopy(replacement)
    return payload


def describe_change(change: dict[str, Any]) -> dict[str, Any]:
    """Attach presentation context without removing the compatibility path."""

    path = change["path"]
    parameter = PARAMETER_BY_ID.get(path)
    if parameter:
        return {**change, "presentation": {key: copy.deepcopy(parameter[key]) for key in ("label", "group", "unit", "where_used")}}
    if path.startswith("overrides."):
        return {
            **change,
            "presentation": {
                "label": "Лётный час / M1 / M2 / M3",
                "group": "flight_hour",
                "unit": "₽ / ч",
                "where_used": ["Лётный час → M1", "Лётный час → M2", "Лётный час → M3"],
            },
        }
    if path.startswith("operations."):
        return {
            **change,
            "presentation": {
                "label": "Расширенная композиция расчёта",
                "group": "advanced",
                "unit": None,
                "where_used": ["Advanced mode"],
            },
        }
    return {**change, "presentation": None}


__all__ = ["apply_business_update", "business_view", "describe_change", "metadata"]
