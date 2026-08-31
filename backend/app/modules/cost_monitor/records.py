from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Any


def _immutable_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(dict(value))


@dataclass(frozen=True)
class TariffRecord:
    """Каноническая tariff row; physical Excel columns остаются в adapter."""

    airport: str
    service: str
    rate: float
    aircraft: str = ""
    identifier: str | None = None
    unit: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    organization: str | None = None
    note: str | None = None
    source: str | None = None
    source_file: str | None = None
    source_row: int | None = None
    legacy_manual: bool | None = None

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> TariffRecord:
        return cls(
            airport=str(value["airport"]),
            service=str(value["service"]),
            rate=float(value["rate"]),
            aircraft=str(value.get("aircraft", "")),
            identifier=str(value["id"]) if value.get("id") is not None else None,
            unit=str(value["unit"]) if value.get("unit") is not None else None,
            start_date=str(value["start_date"]) if value.get("start_date") is not None else None,
            end_date=str(value["end_date"]) if value.get("end_date") is not None else None,
            organization=str(value["organization"]) if value.get("organization") is not None else None,
            note=str(value["note"]) if value.get("note") is not None else None,
            source=str(value["source"]) if value.get("source") is not None else None,
            source_file=str(value["source_file"]) if value.get("source_file") is not None else None,
            source_row=int(value["source_row"]) if value.get("source_row") is not None else None,
            legacy_manual=bool(value["legacy_manual"]) if "legacy_manual" in value else None,
        )

    def to_mapping(self) -> dict[str, Any]:
        result: dict[str, Any] = {"airport": self.airport, "service": self.service, "rate": self.rate, "aircraft": self.aircraft}
        result.update(
            {
                key: value
                for key, value in {
                    "id": self.identifier,
                    "unit": self.unit,
                    "start_date": self.start_date,
                    "end_date": self.end_date,
                    "organization": self.organization,
                    "note": self.note,
                    "source": self.source,
                    "source_file": self.source_file,
                    "source_row": self.source_row,
                    "legacy_manual": self.legacy_manual,
                }.items()
                if value is not None
            }
        )
        return result


@dataclass(frozen=True)
class FuelPriceRecord:
    airport: str
    price: float
    currency: str | None = None
    partner: str | None = None
    price_kind: str | None = None
    period: str | None = None
    source_file: str | None = None
    exchange_rate: float | None = None
    exchange_rate_source: str | None = None
    exchange_rate_timestamp: str | None = None
    exchange_rate_fallback_used: bool | None = None

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> FuelPriceRecord:
        return cls(
            airport=str(value["airport"]),
            price=float(value["price"]),
            currency=str(value["currency"]) if value.get("currency") is not None else None,
            partner=str(value["partner"]) if value.get("partner") is not None else None,
            price_kind=str(value["price_kind"]) if value.get("price_kind") is not None else None,
            period=str(value["period"]) if value.get("period") is not None else None,
            source_file=str(value["source_file"]) if value.get("source_file") is not None else None,
            exchange_rate=float(value["exchange_rate"]) if value.get("exchange_rate") is not None else None,
            exchange_rate_source=str(value["exchange_rate_source"])
            if value.get("exchange_rate_source") is not None
            else None,
            exchange_rate_timestamp=str(value["exchange_rate_timestamp"])
            if value.get("exchange_rate_timestamp") is not None
            else None,
            exchange_rate_fallback_used=bool(value["exchange_rate_fallback_used"])
            if value.get("exchange_rate_fallback_used") is not None
            else None,
        )

    def to_mapping(self) -> dict[str, Any]:
        result: dict[str, Any] = {"airport": self.airport, "price": self.price}
        result.update(
            {
                key: value
                for key, value in {
                    "currency": self.currency,
                    "partner": self.partner,
                    "price_kind": self.price_kind,
                    "period": self.period,
                    "source_file": self.source_file,
                    "exchange_rate": self.exchange_rate,
                    "exchange_rate_source": self.exchange_rate_source,
                    "exchange_rate_timestamp": self.exchange_rate_timestamp,
                    "exchange_rate_fallback_used": self.exchange_rate_fallback_used,
                }.items()
                if value is not None
            }
        )
        return result


@dataclass(frozen=True)
class RouteRecord:
    key: str
    flight_time: float
    distance: float
    departure: str | None = None
    arrival: str | None = None
    source_row: int | None = None

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RouteRecord:
        return cls(
            key=str(value["key"]),
            flight_time=float(value.get("flight_time", 0.0)),
            distance=float(value.get("distance", 0.0)),
            departure=str(value["departure"]) if value.get("departure") is not None else None,
            arrival=str(value["arrival"]) if value.get("arrival") is not None else None,
            source_row=int(value["source_row"]) if value.get("source_row") is not None else None,
        )

    def to_mapping(self) -> dict[str, Any]:
        result: dict[str, Any] = {"key": self.key, "flight_time": self.flight_time, "distance": self.distance}
        result.update(
            {key: value for key, value in {"departure": self.departure, "arrival": self.arrival, "source_row": self.source_row}.items() if value is not None}
        )
        return result


@dataclass(frozen=True)
class MonitorWorkbookData:
    """Нормализованный результат workbook adapter без physical sheet semantics."""

    routes: tuple[RouteRecord, ...]
    international_airports: Mapping[str, bool]
    other_costs: Mapping[str, float]
    aircraft_multipliers: Mapping[str, float]
    scenario_rates: Mapping[str, Mapping[str, tuple[float, float, float]]]
    legacy_manual_tariffs: tuple[TariffRecord, ...]

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> MonitorWorkbookData:
        scenario_rates = {
            str(scenario): {
                str(aircraft): (float(rates[0]), float(rates[1]), float(rates[2]))
                for aircraft, rates in aircraft_rates.items()
            }
            for scenario, aircraft_rates in value.get("scenario_rates", {}).items()
        }
        return cls(
            routes=tuple(RouteRecord.from_mapping(item) for item in value.get("routes", [])),
            international_airports=_immutable_mapping({str(key): bool(flag) for key, flag in value.get("international_airports", {}).items()}),
            other_costs=_immutable_mapping({str(key): float(amount) for key, amount in value.get("other_costs", {}).items()}),
            aircraft_multipliers=_immutable_mapping({str(key): float(amount) for key, amount in value.get("aircraft_multipliers", {}).items()}),
            scenario_rates=MappingProxyType({scenario: _immutable_mapping(rates) for scenario, rates in scenario_rates.items()}),
            legacy_manual_tariffs=tuple(TariffRecord.from_mapping(item) for item in value.get("legacy_manual_tariffs", [])),
        )


@dataclass(frozen=True)
class CostMonitorDataset:
    """Source-agnostic input calculation engine; JSON остаётся на storage boundary."""

    imported_tariffs: tuple[TariffRecord, ...]
    manual_tariffs: tuple[TariffRecord, ...]
    fuel_prices: tuple[FuelPriceRecord, ...]
    routes: tuple[RouteRecord, ...]
    international_airports: Mapping[str, bool]
    other_costs: Mapping[str, float]
    aircraft_multipliers: Mapping[str, float]
    scenario_rates: Mapping[str, Mapping[str, tuple[float, float, float]]]
    data_revision: int = 0

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> CostMonitorDataset:
        scenario_rates = {
            str(scenario): {
                str(aircraft): (float(rates[0]), float(rates[1]), float(rates[2]))
                for aircraft, rates in aircraft_rates.items()
            }
            for scenario, aircraft_rates in state.get("scenario_rates", {}).items()
        }
        return cls(
            imported_tariffs=tuple(TariffRecord.from_mapping(item) for item in state.get("imported_tariffs", [])),
            manual_tariffs=tuple(TariffRecord.from_mapping(item) for item in state.get("manual_tariffs", [])),
            fuel_prices=tuple(FuelPriceRecord.from_mapping(item) for item in state.get("fuel_prices", [])),
            routes=tuple(RouteRecord.from_mapping(item) for item in state.get("routes", [])),
            international_airports=_immutable_mapping({str(key): bool(flag) for key, flag in state.get("international_airports", {}).items()}),
            other_costs=_immutable_mapping({str(key): float(amount) for key, amount in state.get("other_costs", {}).items()}),
            aircraft_multipliers=_immutable_mapping({str(key): float(amount) for key, amount in state.get("aircraft_multipliers", {}).items()}),
            scenario_rates=MappingProxyType({scenario: _immutable_mapping(rates) for scenario, rates in scenario_rates.items()}),
            data_revision=int(state.get("data_revision", 0)),
        )

    @property
    def tariffs(self) -> tuple[TariffRecord, ...]:
        """Imported rows precede manual rows to preserve Excel first-match semantics."""

        return self.imported_tariffs + self.manual_tariffs

    def with_srv_tariffs(self, tariffs: tuple[TariffRecord, ...]) -> CostMonitorDataset:
        return replace(self, imported_tariffs=tariffs)

    def with_fuel_prices(self, prices: tuple[FuelPriceRecord, ...]) -> CostMonitorDataset:
        return replace(self, fuel_prices=prices)

    def with_monitor_workbook(self, workbook: MonitorWorkbookData) -> CostMonitorDataset:
        manual_tariffs = tuple(item for item in self.manual_tariffs if not item.legacy_manual) + workbook.legacy_manual_tariffs
        return replace(
            self,
            routes=workbook.routes,
            international_airports=workbook.international_airports,
            other_costs=workbook.other_costs,
            aircraft_multipliers=workbook.aircraft_multipliers,
            scenario_rates=workbook.scenario_rates,
            manual_tariffs=manual_tariffs,
        )

    def write_to_state(self, state: dict[str, Any]) -> None:
        """Serializes only canonical dataset data back to the local storage adapter."""

        state.update(
            {
                "imported_tariffs": [tariff.to_mapping() for tariff in self.imported_tariffs],
                "manual_tariffs": [tariff.to_mapping() for tariff in self.manual_tariffs],
                "fuel_prices": [price.to_mapping() for price in self.fuel_prices],
                "routes": [route.to_mapping() for route in self.routes],
                "international_airports": dict(self.international_airports),
                "other_costs": dict(self.other_costs),
                "aircraft_multipliers": dict(self.aircraft_multipliers),
                "scenario_rates": {
                    scenario: {aircraft: list(rates) for aircraft, rates in aircraft_rates.items()}
                    for scenario, aircraft_rates in self.scenario_rates.items()
                },
            }
        )
