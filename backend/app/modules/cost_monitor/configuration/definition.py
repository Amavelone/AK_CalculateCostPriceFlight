from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceDefinition:
    id: str
    label: str
    description: str
    parser: str
    default_mask: str


SOURCE_DEFINITIONS = (
    SourceDefinition("srv", "Тарифы SRV", "Тарифы услуг аэропортов", "srv_tariffs", "7480_srv*.xlsx"),
    SourceDefinition("fuel_registry", "Реестр керосина", "Выгрузка 1С цен поставщиков", "fuel_registry", "реестр*.xlsx"),
    SourceDefinition(
        "monitor_workbook",
        "Рабочая книга монитора",
        "Маршруты, признак МВЛ и исходные параметры",
        "monitor_workbook",
        "Расчет себестоимости рейсов*.xlsx",
    ),
)

# Bootstrap data is module-owned DATA used only before the first workbook
# activation. It is intentionally not runtime calculation configuration.
DEFAULT_AIRCRAFT_MULTIPLIERS = {"733": 1.0, "737": 1.0, "738": 1.0}
DEFAULT_SCENARIO_RATES = {
    "ГБ 2026": {
        "733": (78.48, 220.45, 272.17),
        "737": (120.0, 280.0, 340.0),
        "738": (165.73, 341.48, 391.28),
    },
    "Оперативная 2026": {
        "733": (78.48, 220.45, 272.17),
        "737": (120.0, 280.0, 340.0),
        "738": (165.73, 341.48, 391.28),
    },
}

REGISTERED_PARAMETER_PATHS = frozenset(
    {
        "fuel.consumption_tons_per_hour",
        "ano.route_rate_per_100_km",
        "catering.base_units",
        "catering.base_unit_rate",
        "catering.passenger_surcharge",
        "vat.rate",
        "vat.airports",
        "ground.split_divisor",
        "ground.stairs_units",
        "ground.telebridge_minutes",
        "ground.transport_passenger_block",
        "ground.fire_truck_rate",
    }
)

LOOKUP_ARGUMENTS = {
    "airport_tariff": frozenset({"airport", "service"}),
    "aircraft_multiplier": frozenset({"aircraft"}),
    "scenario_rate": frozenset({"scenario", "aircraft", "level"}),
}

__all__ = [
    "DEFAULT_AIRCRAFT_MULTIPLIERS",
    "DEFAULT_SCENARIO_RATES",
    "LOOKUP_ARGUMENTS",
    "REGISTERED_PARAMETER_PATHS",
    "SOURCE_DEFINITIONS",
    "SourceDefinition",
]
