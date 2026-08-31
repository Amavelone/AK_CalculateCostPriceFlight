from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .defaults import upgrade_legacy_payload
from .definition import LOOKUP_ARGUMENTS, REGISTERED_PARAMETER_PATHS
from .schema import ConstantValue, CostMonitorConfiguration, LookupValue, ParameterValue, ValueReference, VariableValue
from .variables import REGISTERED_VARIABLE_NAMES, REGISTERED_VARIABLES

VARIABLE_TYPES = {item.name: item.value_type for item in REGISTERED_VARIABLES}


def parameter_value(configuration: CostMonitorConfiguration, path: str) -> Any:
    value: Any = configuration
    for segment in path.split("."):
        value = getattr(value, segment)
    return value


def _validate_reference(reference: ValueReference) -> None:
    if isinstance(reference, VariableValue) and reference.name not in REGISTERED_VARIABLE_NAMES:
        raise ValueError(f"Неизвестная variable: {reference.name}")
    if isinstance(reference, ParameterValue) and reference.path not in REGISTERED_PARAMETER_PATHS:
        raise ValueError(f"Неизвестный parameter: {reference.path}")
    if isinstance(reference, LookupValue):
        expected = LOOKUP_ARGUMENTS.get(reference.name)
        if expected is None:
            raise ValueError(f"Неизвестный lookup: {reference.name}")
        if frozenset(reference.arguments) != expected:
            raise ValueError(f"Lookup {reference.name} требует arguments: {', '.join(sorted(expected))}")
        for argument in reference.arguments.values():
            _validate_reference(argument)


def _reference_type(reference: ValueReference) -> str:
    if isinstance(reference, ConstantValue):
        if isinstance(reference.value, bool):
            return "boolean"
        if isinstance(reference.value, (int, float)):
            return "number"
        if isinstance(reference.value, tuple):
            return "collection"
        return "string"
    if isinstance(reference, VariableValue):
        value_type = VARIABLE_TYPES[reference.name]
        return "number" if value_type == "integer" else value_type.split(":", maxsplit=1)[0]
    if isinstance(reference, ParameterValue):
        return "collection" if reference.path == "vat.airports" else "number"
    return "number"


def _validate_operations(configuration: CostMonitorConfiguration) -> None:
    total_parts = 0
    for step_name in ("ano", "catering", "vat"):
        step = getattr(configuration.operations, step_name)
        ids = [part.id for part in step.parts]
        if len(set(ids)) != len(ids):
            raise ValueError(f"operations.{step_name}.parts содержит duplicate id")
        total_parts += len(step.parts)
        for part in step.parts:
            _validate_reference(part.initial)
            if _reference_type(part.initial) != "number":
                raise ValueError(f"{part.id}.initial должен быть numeric")
            for action in part.operations:
                if action.operation == "round":
                    if action.operand is not None or action.digits is None:
                        raise ValueError("round operation требует digits и не принимает operand")
                    continue
                if action.operand is None or action.digits is not None:
                    raise ValueError(f"{action.operation} operation требует operand и не принимает digits")
                _validate_reference(action.operand)
                if _reference_type(action.operand) != "number":
                    raise ValueError(f"{part.id}.{action.operation}.operand должен быть numeric")
                if action.operation == "divide":
                    if action.operand.kind == "constant" and action.operand.value == 0:
                        raise ValueError("division by zero запрещён в configuration")
                    if action.operand.kind == "parameter" and parameter_value(configuration, action.operand.path) == 0:
                        raise ValueError("division by zero parameter запрещён в configuration")
            if part.condition:
                for group in part.condition.any_of:
                    for clause in group.all_of:
                        _validate_reference(clause.left)
                        _validate_reference(clause.right)
                        left_type = _reference_type(clause.left)
                        right_type = _reference_type(clause.right)
                        if clause.operator in {"gt", "gte", "lt", "lte"} and (
                            left_type != "number" or right_type != "number"
                        ):
                            raise ValueError(f"Condition {clause.operator} требует numeric operands")
                        if clause.operator in {"in", "not_in"} and right_type != "collection":
                            raise ValueError(f"Condition {clause.operator} требует collection справа")
    if total_parts > 64:
        raise ValueError("Operation configuration превышает limit 64 parts")


def validate_configuration(value: CostMonitorConfiguration | Mapping[str, Any]) -> CostMonitorConfiguration:
    """Validates types, registries and module-specific semantic restrictions."""

    configuration = (
        value
        if isinstance(value, CostMonitorConfiguration)
        else CostMonitorConfiguration.model_validate(upgrade_legacy_payload(value))
    )
    airports = configuration.vat.airports
    if len(set(airports)) != len(airports):
        raise ValueError("vat.airports не должен содержать дубликаты")
    if any(len(airport) != 3 or airport != airport.upper() or not airport.isalpha() for airport in airports):
        raise ValueError("vat.airports должен содержать uppercase IATA codes")

    for aircraft, multiplier in configuration.overrides.aircraft_multipliers.items():
        if not aircraft.strip() or multiplier < 0:
            raise ValueError("aircraft multiplier override требует непустой key и неотрицательное значение")
    for scenario, aircraft_rates in configuration.overrides.scenario_rates.items():
        if not scenario.strip() or not aircraft_rates:
            raise ValueError("scenario override и его aircraft rates не должны быть пустыми")
        for aircraft, rates in aircraft_rates.items():
            if not aircraft.strip() or any(rate < 0 for rate in rates):
                raise ValueError("scenario override rates должны быть неотрицательными")

    _validate_operations(configuration)
    return configuration


__all__ = ["parameter_value", "validate_configuration"]
