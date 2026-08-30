from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .schema import CostMonitorConfiguration


def validate_configuration(value: CostMonitorConfiguration | Mapping[str, Any]) -> CostMonitorConfiguration:
    """Проверяет типы и module-specific semantic restrictions до использования."""

    configuration = (
        value if isinstance(value, CostMonitorConfiguration) else CostMonitorConfiguration.model_validate(value)
    )
    airports = configuration.vat.airports
    if len(set(airports)) != len(airports):
        raise ValueError("vat.airports не должен содержать дубликаты")
    if any(len(airport) != 3 or airport != airport.upper() or not airport.isalpha() for airport in airports):
        raise ValueError("vat.airports должен содержать uppercase IATA codes")
    if not configuration.initial_data.aircraft_multipliers:
        raise ValueError("initial_data.aircraft_multipliers не должен быть пустым")
    if any(
        not aircraft.strip() or multiplier < 0
        for aircraft, multiplier in configuration.initial_data.aircraft_multipliers.items()
    ):
        raise ValueError("aircraft multipliers требуют непустой aircraft key и неотрицательное значение")
    if not configuration.initial_data.scenario_rates:
        raise ValueError("initial_data.scenario_rates не должен быть пустым")
    for scenario, aircraft_rates in configuration.initial_data.scenario_rates.items():
        if not scenario.strip() or not aircraft_rates:
            raise ValueError("scenario и его aircraft rates не должны быть пустыми")
        if any(not aircraft.strip() for aircraft in aircraft_rates):
            raise ValueError("scenario aircraft keys не должны быть пустыми")
        if any(any(rate < 0 for rate in rates) for rates in aircraft_rates.values()):
            raise ValueError("scenario rates должны быть неотрицательными")
    expected_bindings = {
        "srv": "srv_tariffs",
        "fuel_registry": "fuel_registry",
        "monitor_workbook": "monitor_workbook",
    }
    actual_bindings = {binding.id: binding.parser for binding in configuration.source_bindings}
    if actual_bindings != expected_bindings:
        raise ValueError("source bindings должны содержать только обязательные Cost Monitor adapters")
    if any(
        "/" in binding.default_mask
        or "\\" in binding.default_mask
        or not binding.default_mask.lower().endswith(".xlsx")
        for binding in configuration.source_bindings
    ):
        raise ValueError("source default_mask должен быть локальной XLSX маской без пути")
    return configuration


__all__ = ["validate_configuration"]
