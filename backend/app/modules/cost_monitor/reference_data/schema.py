from __future__ import annotations

from math import isfinite
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RouteReference(BaseModel):
    """One editable route; key is derived from the two stored endpoint codes."""

    model_config = ConfigDict(extra="forbid")

    departure: str = Field(min_length=1, max_length=20)
    arrival: str = Field(min_length=1, max_length=20)
    distance: float = Field(ge=0)
    flight_time: float = Field(ge=0)
    source_row: int | None = Field(default=None, ge=1)

    @field_validator("departure", "arrival")
    @classmethod
    def normalize_endpoint(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("Route endpoint must not be blank")
        return normalized

    @field_validator("distance", "flight_time")
    @classmethod
    def finite_value(cls, value: float) -> float:
        if not isfinite(value):
            raise ValueError("Reference values must be finite")
        return value

    @property
    def key(self) -> str:
        return f"{self.departure}-{self.arrival}"


class AirportOtherCost(BaseModel):
    """One non-negative airport-level fixed ground cost."""

    model_config = ConfigDict(extra="forbid")

    airport: str = Field(min_length=1, max_length=20)
    amount: float = Field(ge=0)

    @field_validator("airport")
    @classmethod
    def normalize_airport(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("Airport must not be blank")
        return normalized

    @field_validator("amount")
    @classmethod
    def finite_amount(cls, value: float) -> float:
        if not isfinite(value):
            raise ValueError("Reference values must be finite")
        return value


class CostMonitorReferenceData(BaseModel):
    """Bounded Cost Monitor reference catalog, deliberately not a generic framework."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    routes: list[RouteReference] = Field(default_factory=list, max_length=5_000)
    airport_other_costs: list[AirportOtherCost] = Field(default_factory=list, max_length=1_000)

    @model_validator(mode="after")
    def validate_unique_keys(self) -> CostMonitorReferenceData:
        route_keys = [item.key for item in self.routes]
        if len(route_keys) != len(set(route_keys)):
            raise ValueError("Reference routes contain duplicate route key")
        airports = [item.airport for item in self.airport_other_costs]
        if len(airports) != len(set(airports)):
            raise ValueError("Reference airport other costs contain duplicate airport")
        return self


__all__ = ["AirportOtherCost", "CostMonitorReferenceData", "RouteReference"]
