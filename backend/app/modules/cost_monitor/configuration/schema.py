from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ConfigurationModel(BaseModel):
    """Общая строгая граница code-owned configuration definition."""

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


class InitialData(ConfigurationModel):
    aircraft_multipliers: dict[str, float]
    scenario_rates: dict[str, dict[str, tuple[float, float, float]]]


class SourceBinding(ConfigurationModel):
    id: Literal["srv", "fuel_registry", "monitor_workbook"]
    label: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=300)
    parser: Literal["srv_tariffs", "fuel_registry", "monitor_workbook"]
    default_mask: str = Field(min_length=1, max_length=120)


class CostMonitorConfiguration(ConfigurationModel):
    """Разрешённая схема Cost Monitor без arbitrary expressions или I/O."""

    schema_version: Literal["1.0"]
    fuel: FuelParameters
    ano: AnoParameters
    catering: CateringParameters
    vat: VatParameters
    ground: GroundParameters
    initial_data: InitialData
    source_bindings: tuple[SourceBinding, ...] = Field(min_length=3, max_length=3)
