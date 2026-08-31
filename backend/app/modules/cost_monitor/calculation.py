from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from math import ceil
from typing import Any

from .catalog import normalize_key
from .configuration import (
    BASELINE_CONFIGURATION,
    CostMonitorConfiguration,
    EffectiveCalculationContext,
    execute_step,
)
from .records import CostMonitorDataset, RouteRecord, TariffRecord
from .schemas import CalculationRequest, LegInput


def round_currency(value: float) -> float:
    return round(value, 2)


def diagnostic_for_warning(warning: str, departure: str, route_key: str) -> dict[str, str | None]:
    """Сохраняет legacy warning и добавляет стабильную структуру для API clients."""

    if warning.startswith("Заполните аэропорты"):
        return {"code": "missing_airport", "severity": "warning", "component": "input", "reference": None, "message": warning}
    if warning.startswith("Маршрут "):
        return {"code": "missing_route", "severity": "warning", "component": "route", "reference": route_key, "message": warning}
    if "керосина АК" in warning:
        return {"code": "missing_fuel_price", "severity": "warning", "component": "fuel", "reference": departure, "message": warning}
    if warning.startswith("Не найдена ставка АНО"):
        return {"code": "missing_ano_rate", "severity": "warning", "component": "ano", "reference": departure, "message": warning}
    if warning.startswith("Не найдена ставка"):
        return {"code": "missing_tariff", "severity": "warning", "component": "fuel", "reference": departure, "message": warning}
    if warning.startswith("Для типа ВС") and "коэффициент" in warning:
        return {"code": "missing_aircraft_multiplier", "severity": "warning", "component": "ground", "reference": None, "message": warning}
    return {"code": "missing_scenario_rate", "severity": "warning", "component": "margin", "reference": None, "message": warning}


def first_rate(index: dict[str, TariffRecord], airport: str, service: str) -> TariffRecord | None:
    return index.get(f"{airport}-{service}")


def build_tariff_index(dataset: CostMonitorDataset) -> dict[str, TariffRecord]:
    index: dict[str, TariffRecord] = {}
    # `setdefault` намеренно сохраняет первую физическую строку — это повторяет
    # действующее поведение ВПР Excel по таблице ЦРТ_Check.
    for tariff in dataset.tariffs:
        index.setdefault(f"{tariff.airport}-{tariff.service}", tariff)
    return index


@dataclass(frozen=True)
class LegContext:
    departure: str
    arrival: str
    route_key: str
    flight_time: float
    distance: float
    has_route: bool
    fuel_tons: float
    line_type: str
    is_techstop: bool


def resolve_leg_context(
    dataset: CostMonitorDataset,
    leg: LegInput,
    request: CalculationRequest,
    configuration: CostMonitorConfiguration,
) -> tuple[LegContext, list[str]]:
    """Подготавливает lookup-контекст плеча, сохраняя Excel first-match маршрута."""

    departure = normalize_key(leg.departure)
    arrival = normalize_key(leg.arrival)
    route_key = f"{departure}-{arrival}"
    routes: dict[str, RouteRecord] = {}
    for candidate in dataset.routes:
        routes.setdefault(candidate.key, candidate)
    route = routes.get(route_key)
    warnings: list[str] = []
    if not departure or not arrival:
        warnings.append("Заполните аэропорты вылета и посадки.")
    if route is None and departure and arrival:
        warnings.append(f"Маршрут {route_key} не найден в ИШР: налет принят равным 0.")

    flight_time = route.flight_time if route else 0.0
    return (
        LegContext(
            departure=departure,
            arrival=arrival,
            route_key=route_key,
            flight_time=flight_time,
            distance=route.distance if route else 0.0,
            has_route=route is not None,
            fuel_tons=flight_time * configuration.fuel.consumption_tons_per_hour,
            line_type="ВВЛ",
            is_techstop=request.settings.techstop_leg_id == leg.id,
        ),
        warnings,
    )


def add_service(
    details: list[dict[str, Any]],
    tariff_index: dict[str, TariffRecord],
    diagnostics: list[dict[str, str | None]],
    airport: str,
    service: str,
    volume: float,
    divisor: float = 1,
) -> float:
    """Рассчитывает строку НО по правилу Excel: объём × ставка ÷ делитель.

    Если тариф или объём отсутствует, строка не добавляется в детализацию и
    возвращается ноль, как в действующей книге.
    """

    if not volume:
        return 0.0
    tariff = first_rate(tariff_index, airport, service)
    if not tariff:
        diagnostics.append(
            {
                "code": "GROUND_TARIFF_MISSING",
                "severity": "warning",
                "component": "ground",
                "reference": f"{airport}/{service}",
                "message": f"Не найден тариф наземного обслуживания {service} для {airport}.",
            }
        )
        return 0.0
    amount = volume * tariff.rate / divisor
    details.append(
        {
            "airport": airport,
            "service": service,
            "rate": tariff.rate,
            "volume": volume,
            "divisor": divisor,
            "amount": amount,
        }
    )
    return amount


def calculate_ground(
    dataset: CostMonitorDataset,
    leg: LegInput,
    tariff_index: dict[str, TariffRecord],
    is_techstop: bool,
    effective: EffectiveCalculationContext,
) -> tuple[float, list[dict[str, Any]], list[dict[str, str | None]]]:
    """Воспроизводит обычный и техстоповый блоки НО действующей книги.

    Release v1 поддерживает только ВВЛ; порядок добавления сохраняет first-match
    semantics Excel для approved domestic baseline.
    """

    departure = normalize_key(leg.departure)
    arrival = normalize_key(leg.arrival)
    configuration = effective.configuration
    aircraft_factor = float(effective.aircraft_multiplier(leg.aircraft).value)
    details: list[dict[str, Any]] = []
    diagnostics: list[dict[str, str | None]] = []

    if is_techstop:
        # Строки НО 33:38. Пожарная машина — фиксированное значение текущей книги.
        ground = 0.0
        ground += add_service(details, tariff_index, diagnostics, departure, "ВЗЛЕТ-ПОСАДКА", aircraft_factor)
        ground += add_service(details, tariff_index, diagnostics, departure, "ТРАНСПБЕЗОП", aircraft_factor)
        ground += add_service(details, tariff_index, diagnostics, departure, "ПРИЕМ-ВЫПУСК", 1)
        ground += add_service(details, tariff_index, diagnostics, departure, "БУКСИРОВКА", 1)
        ground += add_service(
            details,
            tariff_index,
            diagnostics,
            departure,
            "ТРАП",
            configuration.ground.stairs_units,
            divisor=configuration.ground.split_divisor,
        )
        fire_truck = configuration.ground.fire_truck_rate / configuration.ground.split_divisor
        details.append(
            {
                "airport": departure,
                "service": "ПОЖАРНАЯ МАШИНА",
                "rate": configuration.ground.fire_truck_rate,
                "volume": 1,
                "divisor": configuration.ground.split_divisor,
                "amount": fire_truck,
            }
        )
        return ground + fire_truck, details, diagnostics

    passenger_volume = float(leg.passengers)
    terminal_departure = passenger_volume
    terminal_arrival = passenger_volume
    ground = 0.0
    ground += add_service(details, tariff_index, diagnostics, departure, "ВЗЛЕТ-ПОСАДКА", aircraft_factor)
    ground += add_service(details, tariff_index, diagnostics, departure, "ТРАНСПБЕЗОП", aircraft_factor)
    ground += add_service(details, tariff_index, diagnostics, departure, "ПАССАЖИР", passenger_volume)
    ground += add_service(details, tariff_index, diagnostics, departure, "АЭРОВОКЗАЛ", terminal_departure)
    ground += add_service(details, tariff_index, diagnostics, arrival, "АЭРОВОКЗАЛ", terminal_arrival)
    ground += add_service(details, tariff_index, diagnostics, departure, "ПРИЕМ-ВЫПУСК", 1)
    ground += add_service(details, tariff_index, diagnostics, departure, "БУКСИРОВКА", 1)
    ground += add_service(
        details,
        tariff_index,
        diagnostics,
        departure,
        "ТЕЛЕТРАП МИН",
        configuration.ground.telebridge_minutes,
        divisor=configuration.ground.split_divisor,
    )
    transport_volume = ceil(
        (terminal_departure + terminal_arrival) / configuration.ground.transport_passenger_block
    )
    ground += add_service(
        details,
        tariff_index,
        diagnostics,
        departure,
        "ТРАНСПОРТ",
        transport_volume,
        divisor=configuration.ground.split_divisor,
    )
    ground += add_service(
        details,
        tariff_index,
        diagnostics,
        departure,
        "ТРАП",
        configuration.ground.stairs_units,
        divisor=configuration.ground.split_divisor,
    )
    ground += add_service(details, tariff_index, diagnostics, arrival, "УБОРКА", 1)
    ground += add_service(details, tariff_index, diagnostics, departure, "ВОДА", 1)
    ground += add_service(details, tariff_index, diagnostics, departure, "САНУЗЕЛ", 1)
    ground += add_service(details, tariff_index, diagnostics, departure, "БОРТПИТАНИЕ", 1)
    ground += add_service(details, tariff_index, diagnostics, arrival, "СЛИВ ВОДЫ", 1)

    other = float(dataset.other_costs.get(departure, 0.0))
    if other:
        details.append(
            {"airport": departure, "service": "ПРОЧЕЕ", "rate": other, "volume": 1, "divisor": 1, "amount": other}
        )
        ground += other
    return ground, details, diagnostics


def calculate_leg(
    dataset: CostMonitorDataset,
    leg: LegInput,
    request: CalculationRequest,
    tariff_index: dict[str, TariffRecord],
    effective: EffectiveCalculationContext,
) -> dict[str, Any]:
    configuration = effective.configuration
    context, warnings = resolve_leg_context(dataset, leg, request, configuration)
    departure = context.departure
    arrival = context.arrival
    route_key = context.route_key
    flight_time = context.flight_time
    distance = context.distance
    fuel_tons = context.fuel_tons
    line_type = context.line_type
    is_techstop = context.is_techstop

    fuel = 0.0
    fuel_detail: list[dict[str, Any]] = []
    fuel_provenance: list[dict[str, Any]] = []
    if request.settings.fuel_source == "АК":
        fuel_prices = {record.airport: record for record in dataset.fuel_prices}
        price = fuel_prices.get(departure)
        if price:
            fuel = price.price * fuel_tons
            fuel_detail.append(
                {
                    "airport": departure,
                    "service": "Керосин АК",
                    "rate": price.price,
                    "volume": fuel_tons,
                    "divisor": 1,
                    "amount": fuel,
                }
            )
            fuel_provenance.append(
                {
                    "airport": price.airport,
                    "origin": "source",
                    "source_file": price.source_file,
                    "currency": price.currency,
                    "exchange_rate": price.exchange_rate,
                    "exchange_rate_source": price.exchange_rate_source,
                    "exchange_rate_timestamp": price.exchange_rate_timestamp,
                    "exchange_rate_fallback_used": price.exchange_rate_fallback_used,
                }
            )
        elif departure:
            warnings.append(f"Не найдена цена керосина АК для {departure}.")
    else:
        for service in ("КЕРОСИН", "ЗАПРАВКА ВС"):
            tariff = first_rate(tariff_index, departure, service)
            if not tariff:
                if departure:
                    warnings.append(f"Не найдена ставка {service} для {departure}.")
                continue
            # КЕРОСИН и ЗАПРАВКА ВС используют объём топлива в тоннах в строках
            # НО 3–4 и в соответствующих строках техстопа 30–31.
            volume = fuel_tons
            amount = tariff.rate * volume
            fuel += amount
            fuel_detail.append(
                {
                    "airport": departure,
                    "service": service,
                    "rate": tariff.rate,
                    "volume": volume,
                    "divisor": 1,
                    "amount": amount,
                }
            )
            fuel_provenance.append(
                {
                    "airport": tariff.airport,
                    "service": tariff.service,
                    "origin": "source",
                    "source_file": tariff.source_file,
                    "source_row": tariff.source_row,
                }
            )

    ground, ground_detail, ground_diagnostics = calculate_ground(
        dataset,
        leg,
        tariff_index,
        is_techstop,
        effective,
    )

    ano_tariff = first_rate(tariff_index, departure, "АНО АД")
    aircraft_multiplier_value = effective.aircraft_multiplier(leg.aircraft)
    aircraft_multiplier = float(aircraft_multiplier_value.value)
    ano_execution = execute_step(
        configuration.operations.ano,
        effective,
        {
            "departure": departure,
            "arrival": arrival,
            "aircraft": leg.aircraft,
            "distance": distance,
            "has_route": context.has_route,
            "has_ano_tariff": ano_tariff is not None,
        },
    )
    ano = ano_execution.amount
    ano_detail: list[dict[str, Any]] = []
    if ano_tariff and context.has_route:
        airport_ano = ano_execution.parts.get("airport_ano", 0.0)
        route_ano = ano_execution.parts.get("route_ano", 0.0)
        ano_detail = [
            {
                "airport": departure,
                "service": "АНО АД",
                "rate": ano_tariff.rate,
                "volume": aircraft_multiplier,
                "divisor": 1,
                "amount": airport_ano,
            },
            {
                "airport": route_key,
                "service": "МАРШРУТНАЯ ЧАСТЬ АНО",
                "rate": configuration.ano.route_rate_per_100_km,
                "volume": distance / 100,
                "divisor": 1,
                "amount": route_ano,
            },
        ]
    if not ano_tariff and departure:
        warnings.append(f"Не найдена ставка АНО АД для {departure}; компонент АНО принят равным 0.")
    if leg.aircraft not in configuration.overrides.aircraft_multipliers:
        warnings.append(f"Для типа ВС {leg.aircraft} отсутствует коэффициент в Calculation Configuration.")

    base_catering_nonzero = bool(
        configuration.catering.base_units * configuration.catering.base_unit_rate
    )
    catering_execution = execute_step(
        configuration.operations.catering,
        effective,
        {
            "departure": departure,
            "arrival": arrival,
            "aircraft": leg.aircraft,
            "passengers": leg.passengers,
            "has_route_key": bool(route_key and route_key != "-"),
            "catering_enabled": request.settings.catering,
            "base_catering_nonzero": base_catering_nonzero,
        },
    )
    catering = catering_execution.amount
    catering_detail: list[dict[str, Any]] = []
    base_catering = catering_execution.parts.get("base_catering", 0.0)
    if base_catering:
        catering_detail.append(
            {
                "airport": departure,
                "service": "БАЗОВОЕ БОРТПИТАНИЕ",
                "rate": configuration.catering.base_unit_rate,
                "volume": configuration.catering.base_units,
                "divisor": 1,
                "amount": base_catering,
            }
        )
    passenger_catering = catering_execution.parts.get("passenger_catering", 0.0)
    if passenger_catering:
        catering_detail.append(
            {
                "airport": departure,
                "service": "ДОПЛАТА ЗА ПАССАЖИРОВ",
                "rate": configuration.catering.passenger_surcharge,
                "volume": leg.passengers,
                "divisor": 1,
                "amount": passenger_catering,
            }
        )
    known_catering_parts = {"base_catering", "passenger_catering"}
    for part in configuration.operations.catering.parts:
        amount = catering_execution.parts.get(part.id, 0.0)
        if part.id not in known_catering_parts and amount:
            catering_detail.append(
                {
                    "airport": departure,
                    "service": part.detail_service,
                    "rate": amount,
                    "volume": 1,
                    "divisor": 1,
                    "amount": amount,
                }
            )

    vat_execution = execute_step(
        configuration.operations.vat,
        effective,
        {
            "departure": departure,
            "arrival": arrival,
            "line_type": line_type,
            "fuel": fuel,
            "ground": ground,
            "ano": ano,
            "catering": catering,
        },
    )
    vat_base = fuel + ground + ano + catering
    vat = vat_execution.amount
    vat_applies = any(item.get("applied") for item in vat_execution.trace)
    vat_detail: list[dict[str, Any]] = []
    if vat_applies:
        for service, amount in (
            ("ГСМ В БАЗЕ НДС", fuel),
            ("НАЗЕМНОЕ ОБСЛУЖИВАНИЕ В БАЗЕ НДС", ground),
            ("АНО В БАЗЕ НДС", ano),
            ("БОРТПИТАНИЕ В БАЗЕ НДС", catering),
        ):
            vat_detail.append({"airport": route_key, "service": service, "rate": 1, "volume": amount, "divisor": 1, "amount": amount})
        vat_detail.extend(
            [
                {"airport": route_key, "service": "НАЛОГОВАЯ БАЗА", "rate": 1, "volume": vat_base, "divisor": 1, "amount": vat_base},
                {
                    "airport": route_key,
                    "service": "НДС",
                    "rate": configuration.vat.rate,
                    "volume": vat_base,
                    "divisor": 1,
                    "amount": vat,
                },
            ]
        )

    configured_scenario = configuration.overrides.scenario_rates.get(request.settings.scenario, {})
    rate_values = [effective.scenario_rate(request.settings.scenario, leg.aircraft, level) for level in range(3)]
    rates = tuple(float(value.value) for value in rate_values)
    if leg.aircraft not in configured_scenario:
        warnings.append(f"Для типа ВС {leg.aircraft} нет ставок М1/М2/М3 в сценарии «{request.settings.scenario}».")
    margins = [float(rate) * flight_time * 1000 for rate in rates]
    base_cost = fuel + ground + ano + catering + vat

    raw_totals = {
        "m1": base_cost + margins[0],
        "m2": base_cost + margins[1],
        "m3": base_cost + margins[2],
    }

    diagnostics = [diagnostic_for_warning(warning, departure, route_key) for warning in warnings]
    diagnostics.extend(ground_diagnostics)
    trace_steps = [
        {
            "stage": "input",
            "component": "leg",
            "operation": None,
            "values": {
                "departure": departure,
                "arrival": arrival,
                "aircraft": leg.aircraft,
                "passengers": leg.passengers,
                "fuel_source": request.settings.fuel_source,
                "scenario": request.settings.scenario,
            },
        },
        {
            "stage": "lookup",
            "component": "route",
            "operation": "first_match",
            "values": {
                "route_key": route_key,
                "found": context.has_route,
                "flight_time": flight_time,
                "distance": distance,
                "line_type": line_type,
            },
        },
    ]
    trace_steps.extend(
        [
            {
                "stage": "parameters",
                "component": "fuel",
                "operation": None,
                "values": {
                    "consumption_tons_per_hour": configuration.fuel.consumption_tons_per_hour,
                    "origin": effective.configuration_origin,
                },
            },
            {
                "stage": "operation",
                "component": "fuel",
                "operation": "multiply",
                "values": {
                    "fuel_tons": fuel_tons,
                    "detail_rows": len(fuel_detail),
                    "provenance": fuel_provenance,
                },
            },
            {"stage": "result", "component": "fuel", "operation": None, "values": {"amount": fuel}},
            {
                "stage": "parameters",
                "component": "ground",
                "operation": None,
                "values": {
                    **configuration.ground.model_dump(mode="json"),
                    "aircraft_multiplier": aircraft_multiplier_value.trace(),
                    "origin": effective.configuration_origin,
                },
            },
            {
                "stage": "operation",
                "component": "ground",
                "operation": "sum_service_rows",
                "values": {"is_techstop": is_techstop, "detail_rows": len(ground_detail)},
            },
            {"stage": "result", "component": "ground", "operation": None, "values": {"amount": ground}},
            {
                "stage": "parameters",
                "component": "ano",
                "operation": None,
                "values": {
                    "route_rate_per_100_km": configuration.ano.route_rate_per_100_km,
                    "origin": effective.configuration_origin,
                },
            },
            {
                "stage": "operation",
                "component": "ano",
                "operation": "configured_parts_sum",
                "values": {"parts": ano_execution.trace, "aircraft_multiplier": aircraft_multiplier_value.trace()},
            },
            {"stage": "result", "component": "ano", "operation": None, "values": {"amount": ano}},
            {
                "stage": "parameters",
                "component": "catering",
                "operation": None,
                "values": {
                    **configuration.catering.model_dump(mode="json"),
                    "origin": effective.configuration_origin,
                },
            },
            {
                "stage": "operation",
                "component": "catering",
                "operation": "configured_parts_sum",
                "values": {"enabled": request.settings.catering, "parts": catering_execution.trace},
            },
            {"stage": "result", "component": "catering", "operation": None, "values": {"amount": catering}},
            {
                "stage": "parameters",
                "component": "vat",
                "operation": None,
                "values": {
                    "rate": configuration.vat.rate,
                    "airports": list(configuration.vat.airports),
                    "origin": effective.configuration_origin,
                },
            },
            {
                "stage": "operation",
                "component": "vat",
                "operation": "configured_parts_sum",
                "values": {"applies": vat_applies, "base": vat_base, "parts": vat_execution.trace},
            },
            {"stage": "result", "component": "vat", "operation": None, "values": {"amount": vat}},
            {
                "stage": "operation",
                "component": "margin",
                "operation": "multiply",
                "values": {
                    "rates": [value.trace() for value in rate_values],
                    "flight_time": flight_time,
                    "factor": 1000,
                },
            },
            {"stage": "result", "component": "margin", "operation": None, "values": {"m1": margins[0], "m2": margins[1], "m3": margins[2]}},
        ]
    )
    return {
        "id": leg.id,
        "route": route_key,
        "departure": departure,
        "arrival": arrival,
        "aircraft": leg.aircraft,
        "passengers": leg.passengers,
        "flight_time": round(flight_time, 3),
        "distance": round(distance, 1),
        "fuel_tons": round(fuel_tons, 3),
        "line_type": line_type,
        "is_techstop": is_techstop,
        "components": {
            "fuel": round_currency(fuel),
            "ground": round_currency(ground),
            "ano": round_currency(ano),
            "catering": round_currency(catering),
            "vat": round_currency(vat),
            "m1": round_currency(margins[0]),
            "m2": round_currency(margins[1]),
            "m3": round_currency(margins[2]),
        },
        "totals": {level: round_currency(value) for level, value in raw_totals.items()},
        # Поле удаляется перед ответом API. Итоговая строка Excel суммирует
        # формулы полной точности и только затем форматирует результат.
        "_raw_totals": raw_totals,
        "details": {
            "fuel": fuel_detail,
            "ground": ground_detail,
            "ano": ano_detail,
            "catering": catering_detail,
            "vat": vat_detail,
        },
        "warnings": warnings,
        "status": "degraded" if diagnostics else "complete",
        "diagnostics": diagnostics,
        "_trace": trace_steps,
    }


def calculate(
    dataset: CostMonitorDataset,
    request: CalculationRequest,
    configuration: CostMonitorConfiguration = BASELINE_CONFIGURATION,
    config_version: int = 1,
    configuration_state: str = "active",
) -> dict[str, Any]:
    tariff_index = build_tariff_index(dataset)
    effective = EffectiveCalculationContext(
        dataset=dataset,
        configuration=configuration,
        config_version=config_version,
        configuration_state=configuration_state,
        tariff_index=tariff_index,
    )
    legs = [calculate_leg(dataset, leg, request, tariff_index, effective) for leg in request.legs]
    total = {
        level: round_currency(sum(item["_raw_totals"][level] for item in legs))
        for level in ("m1", "m2", "m3")
    }
    trace_legs = []
    for item in legs:
        item.pop("_raw_totals", None)
        trace_legs.append({"leg_id": item["id"], "steps": item.pop("_trace")})
    warnings = [warning for leg in legs for warning in leg["warnings"]]
    diagnostics = [diagnostic for leg in legs for diagnostic in leg["diagnostics"]]
    return {
        "calculated_at": datetime.now(UTC).isoformat(),
        "legs": legs,
        "total": total,
        "warnings": list(dict.fromkeys(warnings)),
        "status": "degraded" if diagnostics else "complete",
        "diagnostics": diagnostics,
        "data_snapshot": {
            "revision": dataset.data_revision,
            "tariffs": len(dataset.imported_tariffs),
            "manual_tariffs": len(dataset.manual_tariffs),
            "fuel_prices": len(dataset.fuel_prices),
            "routes": len(dataset.routes),
        },
        "config_version": config_version,
        "configuration_state": configuration_state,
        "trace": {
            "config_version": config_version,
            "configuration_state": configuration_state,
            "data_revision": dataset.data_revision,
            "legs": trace_legs,
        },
    }
