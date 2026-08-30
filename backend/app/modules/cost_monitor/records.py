from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TariffRecord:
    airport: str
    service: str
    rate: float
    aircraft: str = ""

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> TariffRecord:
        return cls(
            airport=str(value["airport"]),
            service=str(value["service"]),
            rate=float(value["rate"]),
            aircraft=str(value.get("aircraft", "")),
        )


@dataclass(frozen=True)
class FuelPriceRecord:
    airport: str
    price: float

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> FuelPriceRecord:
        return cls(airport=str(value["airport"]), price=float(value["price"]))


@dataclass(frozen=True)
class RouteRecord:
    key: str
    flight_time: float
    distance: float

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RouteRecord:
        return cls(key=str(value["key"]), flight_time=float(value["flight_time"]), distance=float(value["distance"]))
