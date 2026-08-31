from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ConfigurationModel(BaseModel):
    """Строгая сериализуемая граница runtime-конфигурации, принадлежащей модулю."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class FuelParameters(ConfigurationModel):
    consumption_tons_per_hour: float = Field(gt=0, le=100)


class AnoParameters(ConfigurationModel):
    route_rate_per_100_km: float = Field(ge=0, le=100_000_000)


class CateringParameters(ConfigurationModel):
    base_units: int = Field(ge=0, le=1_000)
    base_unit_rate: float = Field(ge=0, le=100_000_000)
    passenger_surcharge: float = Field(ge=0, le=10_000_000)


class VatParameters(ConfigurationModel):
    rate: float = Field(ge=0, le=1)
    airports: tuple[str, ...] = Field(min_length=1, max_length=100)


class GroundParameters(ConfigurationModel):
    split_divisor: float = Field(gt=0, le=1_000)
    stairs_units: float = Field(ge=0, le=1_000)
    telebridge_minutes: float = Field(ge=0, le=24 * 60)
    transport_passenger_block: int = Field(gt=0, le=100_000)
    fire_truck_rate: float = Field(ge=0, le=100_000_000)


class ConstantValue(ConfigurationModel):
    kind: Literal["constant"]
    value: float | str | bool | tuple[str, ...]


class VariableValue(ConfigurationModel):
    kind: Literal["variable"]
    name: str = Field(min_length=1, max_length=80)


class ParameterValue(ConfigurationModel):
    kind: Literal["parameter"]
    path: str = Field(min_length=1, max_length=120)


LookupArgument = Annotated[ConstantValue | VariableValue | ParameterValue, Field(discriminator="kind")]


class LookupValue(ConfigurationModel):
    kind: Literal["lookup"]
    name: str = Field(min_length=1, max_length=80)
    arguments: dict[str, LookupArgument] = Field(default_factory=dict, max_length=8)


ValueReference = Annotated[ConstantValue | VariableValue | ParameterValue | LookupValue, Field(discriminator="kind")]


class OperationAction(ConfigurationModel):
    operation: Literal["add", "subtract", "multiply", "divide", "round"]
    operand: ValueReference | None = None
    digits: int | None = Field(default=None, ge=0, le=8)


class ConditionClause(ConfigurationModel):
    left: ValueReference
    operator: Literal["eq", "ne", "gt", "gte", "lt", "lte", "in", "not_in"]
    right: ValueReference


class ConditionGroup(ConfigurationModel):
    all_of: tuple[ConditionClause, ...] = Field(min_length=1, max_length=12)


class OperationCondition(ConfigurationModel):
    # Группы объединяются через OR, а clauses внутри одной группы — через AND.
    any_of: tuple[ConditionGroup, ...] = Field(min_length=1, max_length=8)


class OperationPart(ConfigurationModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    label: str = Field(min_length=1, max_length=120)
    initial: ValueReference
    operations: tuple[OperationAction, ...] = Field(default_factory=tuple, max_length=16)
    condition: OperationCondition | None = None
    detail_service: str = Field(min_length=1, max_length=120)


class StepOperations(ConfigurationModel):
    parts: tuple[OperationPart, ...] = Field(min_length=1, max_length=32)
    aggregation: Literal["sum"] = "sum"


class CalculationOperations(ConfigurationModel):
    ano: StepOperations
    catering: StepOperations
    vat: StepOperations


class CalculationOverrides(ConfigurationModel):
    aircraft_multipliers: dict[str, float] = Field(default_factory=dict, max_length=200)
    scenario_rates: dict[str, dict[str, tuple[float, float, float]]] = Field(default_factory=dict, max_length=100)


class CostMonitorConfiguration(ConfigurationModel):
    """Разрешённая семантика Cost Monitor без произвольного кода и внешнего I/O."""

    schema_version: Literal["2.0"]
    fuel: FuelParameters
    ano: AnoParameters
    catering: CateringParameters
    vat: VatParameters
    ground: GroundParameters
    operations: CalculationOperations
    overrides: CalculationOverrides = Field(default_factory=CalculationOverrides)


def value_ref(kind: str, **values: Any) -> dict[str, Any]:
    return {"kind": kind, **values}


__all__ = [
    "CalculationOperations",
    "CalculationOverrides",
    "ConditionClause",
    "ConditionGroup",
    "CostMonitorConfiguration",
    "OperationAction",
    "OperationCondition",
    "OperationPart",
    "StepOperations",
    "ValueReference",
    "value_ref",
]
