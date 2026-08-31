from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .schema import CostMonitorConfiguration


def _constant(value: Any) -> dict[str, Any]:
    return {"kind": "constant", "value": value}


def _variable(name: str) -> dict[str, Any]:
    return {"kind": "variable", "name": name}


def _parameter(path: str) -> dict[str, Any]:
    return {"kind": "parameter", "path": path}


def _lookup(name: str, **arguments: dict[str, Any]) -> dict[str, Any]:
    return {"kind": "lookup", "name": name, "arguments": arguments}


def _condition(*groups: tuple[tuple[dict[str, Any], str, dict[str, Any]], ...]) -> dict[str, Any]:
    return {
        "any_of": [
            {"all_of": [{"left": left, "operator": operator, "right": right} for left, operator, right in group]}
            for group in groups
        ]
    }


BASELINE_OPERATIONS: dict[str, Any] = {
    "ano": {
        "aggregation": "sum",
        "parts": [
            {
                "id": "airport_ano",
                "label": "Аэропортовая часть АНО",
                "detail_service": "АНО АД",
                "initial": _lookup(
                    "airport_tariff",
                    airport=_variable("departure"),
                    service=_constant("АНО АД"),
                ),
                "operations": [
                    {
                        "operation": "multiply",
                        "operand": _lookup("aircraft_multiplier", aircraft=_variable("aircraft")),
                    }
                ],
                "condition": _condition(
                    (
                        (_variable("has_route"), "eq", _constant(True)),
                        (_variable("has_ano_tariff"), "eq", _constant(True)),
                    )
                ),
            },
            {
                "id": "route_ano",
                "label": "Маршрутная часть АНО",
                "detail_service": "МАРШРУТНАЯ ЧАСТЬ АНО",
                "initial": _variable("distance"),
                "operations": [
                    {"operation": "divide", "operand": _constant(100)},
                    {"operation": "multiply", "operand": _parameter("ano.route_rate_per_100_km")},
                ],
                "condition": _condition(
                    (
                        (_variable("has_route"), "eq", _constant(True)),
                        (_variable("has_ano_tariff"), "eq", _constant(True)),
                    )
                ),
            },
        ],
    },
    "catering": {
        "aggregation": "sum",
        "parts": [
            {
                "id": "base_catering",
                "label": "Базовое бортпитание",
                "detail_service": "БАЗОВОЕ БОРТПИТАНИЕ",
                "initial": _parameter("catering.base_units"),
                "operations": [
                    {"operation": "multiply", "operand": _parameter("catering.base_unit_rate")}
                ],
                "condition": _condition(((_variable("has_route_key"), "eq", _constant(True)),)),
            },
            {
                "id": "passenger_catering",
                "label": "Доплата за пассажиров",
                "detail_service": "ДОПЛАТА ЗА ПАССАЖИРОВ",
                "initial": _variable("passengers"),
                "operations": [
                    {"operation": "multiply", "operand": _parameter("catering.passenger_surcharge")}
                ],
                "condition": _condition(
                    (
                        (_variable("has_route_key"), "eq", _constant(True)),
                        (_variable("catering_enabled"), "eq", _constant(True)),
                        (_variable("base_catering_nonzero"), "eq", _constant(True)),
                    )
                ),
            },
        ],
    },
    "vat": {
        "aggregation": "sum",
        "parts": [
            {
                "id": "vat",
                "label": "НДС",
                "detail_service": "НДС",
                "initial": _variable("fuel"),
                "operations": [
                    {"operation": "add", "operand": _variable("ground")},
                    {"operation": "add", "operand": _variable("ano")},
                    {"operation": "add", "operand": _variable("catering")},
                    {"operation": "multiply", "operand": _parameter("vat.rate")},
                ],
                "condition": _condition(
                    (
                        (_variable("line_type"), "eq", _constant("ВВЛ")),
                        (_variable("departure"), "in", _parameter("vat.airports")),
                    ),
                    (
                        (_variable("line_type"), "eq", _constant("ВВЛ")),
                        (_variable("arrival"), "in", _parameter("vat.airports")),
                    ),
                ),
            }
        ],
    },
}


BASELINE_CALCULATION_OVERRIDES = {
    "aircraft_multipliers": {"733": 62.822, "738": 79.015},
    "scenario_rates": {
        "ГБ 2026": {
            "733": [78.4821885554647, 220.446814882244, 272.17480053077],
            "738": [165.7264579935, 341.481178756, 391.282636477],
        },
        "Оперативная 2026": {
            "733": [78.48218856, 220.4468149, 272.1748005],
            "738": [161.6316247, 325.8585986, 376.9372549],
        },
    },
}


BASELINE_PAYLOAD: dict[str, Any] = {
    "schema_version": "2.0",
    "fuel": {"consumption_tons_per_hour": 2.7},
    "ano": {"route_rate_per_100_km": 1666.6},
    "catering": {"base_units": 6, "base_unit_rate": 1500, "passenger_surcharge": 500},
    "vat": {"rate": 0.1, "airports": ["DME", "SVO", "VKO"]},
    "ground": {
        "split_divisor": 2,
        "stairs_units": 2,
        "telebridge_minutes": 90,
        "transport_passenger_block": 100,
        "fire_truck_rate": 25132,
    },
    "operations": BASELINE_OPERATIONS,
    "overrides": BASELINE_CALCULATION_OVERRIDES,
}


def upgrade_legacy_payload(value: Mapping[str, Any]) -> dict[str, Any]:
    """Normalizes persisted v1 content without rewriting immutable records."""

    if value.get("schema_version") != "1.0":
        return dict(value)
    return {
        "schema_version": "2.0",
        "fuel": value["fuel"],
        "ano": value["ano"],
        "catering": value["catering"],
        "vat": value["vat"],
        "ground": value["ground"],
        "operations": BASELINE_OPERATIONS,
        "overrides": BASELINE_CALCULATION_OVERRIDES,
    }


BASELINE_CONFIGURATION = CostMonitorConfiguration.model_validate(BASELINE_PAYLOAD)

__all__ = [
    "BASELINE_CALCULATION_OVERRIDES",
    "BASELINE_CONFIGURATION",
    "BASELINE_OPERATIONS",
    "BASELINE_PAYLOAD",
    "upgrade_legacy_payload",
]
