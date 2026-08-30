from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from math import ceil
from typing import Any

from .catalog import normalize_key, tariffs_for_view
from .records import FuelPriceRecord, RouteRecord, TariffRecord
from .schemas import CalculationRequest, LegInput


def round_currency(value: float) -> float:
    return round(value, 2)


def diagnostic_for_warning(warning: str, departure: str, route_key: str) -> dict[str, str | None]:
    """Сохраняет legacy warning и добавляет стабильную структуру для API clients."""

    if warning.startswith("Заполните аэропорты"):
        return {"code": "missing_airport", "component": "input", "reference": None, "message": warning}
    if warning.startswith("Маршрут "):
        return {"code": "missing_route", "component": "route", "reference": route_key, "message": warning}
    if "керосина АК" in warning:
        return {"code": "missing_fuel_price", "component": "fuel", "reference": departure, "message": warning}
    if warning.startswith("Не найдена ставка АНО"):
        return {"code": "missing_ano_rate", "component": "ano", "reference": departure, "message": warning}
    if warning.startswith("Не найдена ставка"):
        return {"code": "missing_tariff", "component": "fuel", "reference": departure, "message": warning}
    if warning.startswith("Для типа ВС") and "коэффициент" in warning:
        return {"code": "missing_aircraft_multiplier", "component": "ground", "reference": None, "message": warning}
    return {"code": "missing_scenario_rate", "component": "margin", "reference": None, "message": warning}


def first_rate(index: dict[str, TariffRecord], airport: str, service: str) -> TariffRecord | None:
    return index.get(f"{airport}-{service}")


def build_tariff_index(state: dict[str, Any]) -> dict[str, TariffRecord]:
    index: dict[str, TariffRecord] = {}
    # `setdefault` намеренно сохраняет первую физическую строку — это повторяет
    # действующее поведение ВПР Excel по таблице ЦРТ_Check.
    for raw_tariff in tariffs_for_view(state):
        tariff = TariffRecord.from_mapping(raw_tariff)
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


def resolve_leg_context(state: dict[str, Any], leg: LegInput, request: CalculationRequest) -> tuple[LegContext, list[str]]:
    """Подготавливает lookup-контекст плеча, сохраняя Excel first-match маршрута."""

    departure = normalize_key(leg.departure)
    arrival = normalize_key(leg.arrival)
    route_key = f"{departure}-{arrival}"
    routes: dict[str, RouteRecord] = {}
    for raw_candidate in state.get("routes", []):
        candidate = RouteRecord.from_mapping(raw_candidate)
        routes.setdefault(candidate.key, candidate)
    route = routes.get(route_key)
    warnings: list[str] = []
    if not departure or not arrival:
        warnings.append("Заполните аэропорты вылета и посадки.")
    if route is None and departure and arrival:
        warnings.append(f"Маршрут {route_key} не найден в ИШР: налет принят равным 0.")

    international = bool(state.get("international_airports", {}).get(departure)) or bool(
        state.get("international_airports", {}).get(arrival)
    )
    flight_time = route.flight_time if route else 0.0
    return (
        LegContext(
            departure=departure,
            arrival=arrival,
            route_key=route_key,
            flight_time=flight_time,
            distance=route.distance if route else 0.0,
            has_route=route is not None,
            fuel_tons=flight_time * 2.7,
            line_type="МВЛ" if international else "ВВЛ",
            is_techstop=request.settings.techstop_leg_id == leg.id,
        ),
        warnings,
    )


def add_service(
    details: list[dict[str, Any]],
    tariff_index: dict[str, TariffRecord],
    airport: str,
    service: str,
    volume: float,
    divisor: float = 1,
) -> float:
    """Рассчитывает строку НО по правилу Excel: объём × ставка ÷ делитель.

    Если тариф или объём отсутствует, строка не добавляется в детализацию и
    возвращается ноль, как в действующей книге.
    """

    tariff = first_rate(tariff_index, airport, service)
    if not tariff or not volume:
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
    state: dict[str, Any],
    leg: LegInput,
    tariff_index: dict[str, TariffRecord],
    line_type: str,
    is_techstop: bool,
) -> tuple[float, list[dict[str, Any]]]:
    """Воспроизводит обычный и техстоповый блоки НО действующей книги.

    Состав услуг, объёмы и делители зависят от типа линии и признака техстопа;
    порядок добавления сохраняет семантику первого совпадения Excel.
    """

    departure = normalize_key(leg.departure)
    arrival = normalize_key(leg.arrival)
    aircraft_factor = float(state.get("aircraft_multipliers", {}).get(leg.aircraft, 0.0))
    details: list[dict[str, Any]] = []

    if is_techstop:
        # Строки НО 33:38. Пожарная машина — фиксированное значение текущей книги.
        ground = 0.0
        ground += add_service(details, tariff_index, departure, "ВЗЛЕТ-ПОСАДКА", aircraft_factor)
        ground += add_service(details, tariff_index, departure, "ТРАНСПБЕЗОП", aircraft_factor)
        ground += add_service(details, tariff_index, departure, "ПРИЕМ-ВЫПУСК", 1)
        ground += add_service(details, tariff_index, departure, "БУКСИРОВКА", 1)
        ground += add_service(details, tariff_index, departure, "ТРАП", 2, divisor=2)
        fire_truck = 25132 / 2
        details.append(
            {
                "airport": departure,
                "service": "ПОЖАРНАЯ МАШИНА",
                "rate": 25132,
                "volume": 1,
                "divisor": 2,
                "amount": fire_truck,
            }
        )
        return ground + fire_truck, details

    # Строки НО 6:24. Пассажирские и аэровокзальные услуги применяются во
    # взаимоисключающих ветках ВВЛ/МВЛ в точности как в Excel.
    is_domestic = line_type == "ВВЛ"
    passenger_volume = float(leg.passengers)
    terminal_departure = passenger_volume if is_domestic else 0.0
    terminal_arrival = passenger_volume if is_domestic else 0.0
    terminal_m_departure = passenger_volume if not is_domestic else 0.0
    terminal_m_arrival = passenger_volume if not is_domestic else 0.0
    ground = 0.0
    ground += add_service(details, tariff_index, departure, "ВЗЛЕТ-ПОСАДКА", aircraft_factor)
    ground += add_service(details, tariff_index, departure, "ТРАНСПБЕЗОП", aircraft_factor)
    ground += add_service(details, tariff_index, departure, "ПАССАЖИР", passenger_volume if is_domestic else 0.0)
    ground += add_service(details, tariff_index, departure, "ПАССАЖИР(М)", passenger_volume if not is_domestic else 0.0)
    ground += add_service(details, tariff_index, departure, "АЭРОВОКЗАЛ", terminal_departure)
    ground += add_service(details, tariff_index, departure, "АЭРОВОКЗАЛ(М)", terminal_m_departure)
    ground += add_service(details, tariff_index, arrival, "АЭРОВОКЗАЛ", terminal_arrival)
    ground += add_service(details, tariff_index, arrival, "АЭРОВОКЗАЛ(М)", terminal_m_arrival)
    ground += add_service(details, tariff_index, departure, "ПРИЕМ-ВЫПУСК", 1)
    ground += add_service(details, tariff_index, departure, "БУКСИРОВКА", 1)
    ground += add_service(details, tariff_index, departure, "ТЕЛЕТРАП МИН", 90, divisor=2)
    transport_volume = ceil((terminal_departure + terminal_m_departure + terminal_arrival + terminal_m_arrival) / 100)
    ground += add_service(details, tariff_index, departure, "ТРАНСПОРТ", transport_volume, divisor=2)
    ground += add_service(details, tariff_index, departure, "ТРАП", 2, divisor=2)
    ground += add_service(details, tariff_index, arrival, "УБОРКА", 1)
    ground += add_service(details, tariff_index, departure, "ВОДА", 1)
    ground += add_service(details, tariff_index, departure, "САНУЗЕЛ", 1)
    ground += add_service(details, tariff_index, departure, "БОРТПИТАНИЕ", 1)
    ground += add_service(details, tariff_index, arrival, "СЛИВ ВОДЫ", 1)

    other = float(state.get("other_costs", {}).get(departure, 0.0))
    if other:
        details.append(
            {"airport": departure, "service": "ПРОЧЕЕ", "rate": other, "volume": 1, "divisor": 1, "amount": other}
        )
        ground += other
    return ground, details


def calculate_leg(
    state: dict[str, Any],
    leg: LegInput,
    request: CalculationRequest,
    tariff_index: dict[str, TariffRecord],
) -> dict[str, Any]:
    context, warnings = resolve_leg_context(state, leg, request)
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
    if request.settings.fuel_source == "АК":
        fuel_prices = {
            record.airport: record for record in (FuelPriceRecord.from_mapping(value) for value in state.get("fuel_prices", []))
        }
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

    ground, ground_detail = calculate_ground(state, leg, tariff_index, line_type, is_techstop)

    ano_tariff = first_rate(tariff_index, departure, "АНО АД")
    aircraft_multiplier = float(state.get("aircraft_multipliers", {}).get(leg.aircraft, 0.0))
    ano = 0.0
    ano_detail: list[dict[str, Any]] = []
    if ano_tariff and context.has_route:
        airport_ano = ano_tariff.rate * aircraft_multiplier
        route_ano = distance / 100 * 1666.6
        ano = airport_ano + route_ano
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
                "rate": 1666.6,
                "volume": distance / 100,
                "divisor": 1,
                "amount": route_ano,
            },
        ]
    if not ano_tariff and departure:
        warnings.append(f"Не найдена ставка АНО АД для {departure}; компонент АНО принят равным 0.")
    if leg.aircraft not in state.get("aircraft_multipliers", {}):
        warnings.append(f"Для типа ВС {leg.aircraft} отсутствует коэффициент из Справочников.")

    catering = 0.0 if not route_key or route_key == "-" else 6 * 1500
    catering_detail: list[dict[str, Any]] = []
    if catering:
        catering_detail.append(
            {"airport": departure, "service": "БАЗОВОЕ БОРТПИТАНИЕ", "rate": 1500, "volume": 6, "divisor": 1, "amount": catering}
        )
    if catering and request.settings.catering:
        passenger_catering = leg.passengers * 500
        catering += passenger_catering
        catering_detail.append(
            {
                "airport": departure,
                "service": "ДОПЛАТА ЗА ПАССАЖИРОВ",
                "rate": 500,
                "volume": leg.passengers,
                "divisor": 1,
                "amount": passenger_catering,
            }
        )

    vat_base = fuel + ground + ano + catering
    vat_applies = line_type == "ВВЛ" and bool({departure, arrival}.intersection({"DME", "SVO", "VKO"}))
    vat = vat_base * 0.1 if vat_applies else 0.0
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
                {"airport": route_key, "service": "НДС", "rate": 0.1, "volume": vat_base, "divisor": 1, "amount": vat},
            ]
        )

    scenario = state.get("scenario_rates", {}).get(request.settings.scenario, {})
    rates = scenario.get(leg.aircraft) or [0.0, 0.0, 0.0]
    if leg.aircraft not in scenario:
        warnings.append(f"Для типа ВС {leg.aircraft} нет ставок М1/М2/М3 в сценарии «{request.settings.scenario}».")
    margins = [float(rate) * flight_time * 1000 for rate in rates]
    base_cost = fuel + ground + ano + catering + vat

    raw_totals = {
        "m1": base_cost + margins[0],
        "m2": base_cost + margins[1],
        "m3": base_cost + margins[2],
    }

    diagnostics = [diagnostic_for_warning(warning, departure, route_key) for warning in warnings]
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
    }


def calculate(state: dict[str, Any], request: CalculationRequest) -> dict[str, Any]:
    tariff_index = build_tariff_index(state)
    legs = [calculate_leg(state, leg, request, tariff_index) for leg in request.legs]
    total = {
        level: round_currency(sum(item["_raw_totals"][level] for item in legs))
        for level in ("m1", "m2", "m3")
    }
    for item in legs:
        item.pop("_raw_totals", None)
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
            "revision": int(state.get("data_revision", 0)),
            "tariffs": len(state.get("imported_tariffs", [])),
            "manual_tariffs": len(state.get("manual_tariffs", [])),
            "fuel_prices": len(state.get("fuel_prices", [])),
            "routes": len(state.get("routes", [])),
        },
    }
