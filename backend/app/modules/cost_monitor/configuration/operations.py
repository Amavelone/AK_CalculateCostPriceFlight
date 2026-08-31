from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .effective import EffectiveCalculationContext, EffectiveValue
from .schema import LookupValue, OperationCondition, StepOperations, ValueReference
from .validation import parameter_value


class OperationExecutionError(ValueError):
    """Проверенную operation нельзя выполнить для переданного контекста."""


@dataclass(frozen=True)
class StepExecution:
    amount: float
    parts: dict[str, float]
    trace: list[dict[str, Any]]


def _resolve_lookup(
    reference: LookupValue,
    effective: EffectiveCalculationContext,
    variables: dict[str, Any],
) -> EffectiveValue:
    arguments = {
        key: _resolve_value(value, effective, variables).value
        for key, value in reference.arguments.items()
    }
    if reference.name == "airport_tariff":
        return effective.airport_tariff(str(arguments["airport"]), str(arguments["service"]))
    if reference.name == "aircraft_multiplier":
        return effective.aircraft_multiplier(str(arguments["aircraft"]))
    if reference.name == "scenario_rate":
        return effective.scenario_rate(
            str(arguments["scenario"]),
            str(arguments["aircraft"]),
            int(arguments["level"]),
        )
    raise OperationExecutionError(f"Не поддерживается lookup {reference.name}")


def _resolve_value(
    reference: ValueReference,
    effective: EffectiveCalculationContext,
    variables: dict[str, Any],
) -> EffectiveValue:
    if reference.kind == "constant":
        return EffectiveValue(reference.value, effective.configuration_origin)
    if reference.kind == "variable":
        if reference.name not in variables:
            raise OperationExecutionError(f"Variable {reference.name} отсутствует в execution context")
        return EffectiveValue(variables[reference.name], "source", reference=reference.name)
    if reference.kind == "parameter":
        return EffectiveValue(
            parameter_value(effective.configuration, reference.path),
            effective.configuration_origin,
            reference=reference.path,
        )
    return _resolve_lookup(reference, effective, variables)


def _condition_matches(
    condition: OperationCondition | None,
    effective: EffectiveCalculationContext,
    variables: dict[str, Any],
) -> bool:
    if condition is None:
        return True

    def clause_matches(clause: Any) -> bool:
        left = _resolve_value(clause.left, effective, variables).value
        right = _resolve_value(clause.right, effective, variables).value
        operations = {
            "eq": lambda: left == right,
            "ne": lambda: left != right,
            "gt": lambda: left > right,
            "gte": lambda: left >= right,
            "lt": lambda: left < right,
            "lte": lambda: left <= right,
            "in": lambda: left in right,
            "not_in": lambda: left not in right,
        }
        try:
            return bool(operations[clause.operator]())
        except (TypeError, KeyError) as error:
            raise OperationExecutionError(f"Condition {clause.operator} несовместим с operand types") from error

    return any(all(clause_matches(clause) for clause in group.all_of) for group in condition.any_of)


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OperationExecutionError(f"{label} должен быть numeric")
    return float(value)


def execute_step(
    step: StepOperations,
    effective: EffectiveCalculationContext,
    variables: dict[str, Any],
) -> StepExecution:
    """Выполняет один проверенный data-defined компонент расчёта.

    Это намеренно небольшой interpreter над whitelist Configuration, а не
    expression evaluator. Trace сохраняет разрешённые значения и порядок action,
    чтобы готовый расчёт можно было аудировать без повторного выполнения.
    """

    parts: dict[str, float] = {}
    trace: list[dict[str, Any]] = []
    for part in step.parts:
        applied = _condition_matches(part.condition, effective, variables)
        if not applied:
            parts[part.id] = 0.0
            trace.append({"id": part.id, "label": part.label, "applied": False, "result": 0.0})
            continue
        initial = _resolve_value(part.initial, effective, variables)
        current = _number(initial.value, f"{part.id}.initial")
        actions: list[dict[str, Any]] = []
        for action in part.operations:
            before = current
            if action.operation == "round":
                current = round(current, int(action.digits or 0))
                actions.append(
                    {"operation": "round", "before": before, "digits": action.digits, "result": current}
                )
                continue
            if action.operand is None:
                raise OperationExecutionError(f"{action.operation} не имеет operand")
            operand = _resolve_value(action.operand, effective, variables)
            operand_number = _number(operand.value, f"{part.id}.{action.operation}.operand")
            if action.operation == "add":
                current += operand_number
            elif action.operation == "subtract":
                current -= operand_number
            elif action.operation == "multiply":
                current *= operand_number
            elif action.operation == "divide":
                if operand_number == 0:
                    raise OperationExecutionError("Division by zero во время calculation")
                current /= operand_number
            actions.append(
                {
                    "operation": action.operation,
                    "before": before,
                    "operand": operand.trace(),
                    "result": current,
                }
            )
        parts[part.id] = current
        trace.append(
            {
                "id": part.id,
                "label": part.label,
                "applied": True,
                "initial": initial.trace(),
                "actions": actions,
                "result": current,
            }
        )
    return StepExecution(sum(parts.values()), parts, trace)


__all__ = ["OperationExecutionError", "StepExecution", "execute_step"]
