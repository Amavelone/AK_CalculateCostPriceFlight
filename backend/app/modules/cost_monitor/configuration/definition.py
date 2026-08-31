from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceDefinition:
    id: str
    label: str
    description: str
    parser: str
    default_mask: str


PRODUCTION_SOURCE_DEFINITIONS = (
    SourceDefinition("srv", "Тарифы SRV", "Тарифы услуг аэропортов", "srv_tariffs", "7480_srv*.xlsx"),
    SourceDefinition("fuel_registry", "Реестр керосина", "Выгрузка 1С цен поставщиков", "fuel_registry", "реестр*.xlsx"),
)

# Legacy Monitor Workbook остаётся доступным DEV-инструментам parity и migration,
# но намеренно отсутствует в production runtime-конфигурации источников.
COMPATIBILITY_SOURCE_DEFINITIONS = (
    SourceDefinition(
        "monitor_workbook",
        "Рабочая книга монитора",
        "Маршруты, признак МВЛ и исходные параметры",
        "monitor_workbook",
        "Расчет себестоимости рейсов*.xlsx",
    ),
)

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
    "LOOKUP_ARGUMENTS",
    "REGISTERED_PARAMETER_PATHS",
    "COMPATIBILITY_SOURCE_DEFINITIONS",
    "PRODUCTION_SOURCE_DEFINITIONS",
    "SourceDefinition",
]
