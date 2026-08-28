from __future__ import annotations

from datetime import datetime, timezone
from math import ceil
from typing import Any

from ..schemas import CalculationRequest, LegInput
from .sources import normalize_key, tariffs_for_view


def round_currency(value: float) -> float:
    return round(value, 2)


def first_rate(index: dict[str, dict[str, Any]], airport: str, service: str) -> dict[str, Any] | None:
    return index.get(f"{airport}-{service}")


def build_tariff_index(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    # `setdefault` intentionally preserves the first physical item, the same
    # current baseline behavior as Excel VLOOKUP against ЦРТ_Check.
    for tariff in tariffs_for_view(state):
        index.setdefault(f"{tariff['airport']}-{tariff['service']}", tariff)
    return index


def add_service(
    details: list[dict[str, Any]],
    tariff_index: dict[str, dict[str, Any]],
    airport: str,
    service: str,
    volume: float,
    divisor: float = 1,
) -> float:
    """Calculate a НО line with Excel's volume × rate ÷ divisor semantics."""

    tariff = first_rate(tariff_index, airport, service)
    if not tariff or not volume:
        return 0.0
    amount = volume * float(tariff["rate"]) / divisor
    details.append({"service": service, "rate": tariff["rate"], "volume": volume, "amount": amount})
    return amount


def calculate_ground(
    state: dict[str, Any],
    leg: LegInput,
    tariff_index: dict[str, dict[str, Any]],
    line_type: str,
    is_techstop: bool,
) -> tuple[float, list[dict[str, Any]]]:
    """Reproduces normal and tech-stop НО blocks from the current workbook."""

    departure = normalize_key(leg.departure)
    arrival = normalize_key(leg.arrival)
    aircraft_factor = float(state.get("aircraft_multipliers", {}).get(leg.aircraft, 0.0))
    details: list[dict[str, Any]] = []

    if is_techstop:
        # НО rows 33:38. The fire truck is a fixed current workbook value.
        ground = 0.0
        ground += add_service(details, tariff_index, departure, "ВЗЛЕТ-ПОСАДКА", aircraft_factor)
        ground += add_service(details, tariff_index, departure, "ТРАНСПБЕЗОП", aircraft_factor)
        ground += add_service(details, tariff_index, departure, "ПРИЕМ-ВЫПУСК", 1)
        ground += add_service(details, tariff_index, departure, "БУКСИРОВКА", 1)
        ground += add_service(details, tariff_index, departure, "ТРАП", 2, divisor=2)
        fire_truck = 25132 / 2
        details.append({"service": "ПОЖАРНАЯ МАШИНА", "rate": 25132, "volume": 1, "amount": fire_truck})
        return ground + fire_truck, details

    # НО rows 6:24. Passenger and terminal services apply in mutually
    # exclusive domestic/international branches exactly as Excel does.
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
        details.append({"service": "ПРОЧЕЕ", "rate": other, "volume": 1, "amount": other})
        ground += other
    return ground, details


def calculate_leg(
    state: dict[str, Any],
    leg: LegInput,
    request: CalculationRequest,
    tariff_index: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    departure = normalize_key(leg.departure)
    arrival = normalize_key(leg.arrival)
    route_key = f"{departure}-{arrival}"
    routes: dict[str, dict[str, Any]] = {}
    for candidate in state.get("routes", []):
        # ИШР is also searched by VLOOKUP, therefore a duplicate route keeps
        # the first physical row rather than the last parsed one.
        routes.setdefault(candidate["key"], candidate)
    route = routes.get(route_key)
    warnings: list[str] = []

    if not departure or not arrival:
        warnings.append("Заполните аэропорты вылета и посадки.")
    if route is None and departure and arrival:
        warnings.append(f"Маршрут {route_key} не найден в ИШР: налет принят равным 0.")

    flight_time = float(route["flight_time"]) if route else 0.0
    distance = float(route["distance"]) if route else 0.0
    fuel_tons = flight_time * 2.7
    is_techstop = request.settings.techstop_leg_id == leg.id

    international = bool(state.get("international_airports", {}).get(departure)) or bool(
        state.get("international_airports", {}).get(arrival)
    )
    line_type = "МВЛ" if international else "ВВЛ"

    fuel = 0.0
    fuel_detail: list[dict[str, Any]] = []
    if request.settings.fuel_source == "АК":
        fuel_prices = {record["airport"]: record for record in state.get("fuel_prices", [])}
        price = fuel_prices.get(departure)
        if price:
            fuel = float(price["price"]) * fuel_tons
            fuel_detail.append({"service": "Керосин АК", "rate": price["price"], "volume": fuel_tons, "amount": fuel})
        elif departure:
            warnings.append(f"Не найдена цена керосина АК для {departure}.")
    else:
        for service in ("КЕРОСИН", "ЗАПРАВКА ВС"):
            tariff = first_rate(tariff_index, departure, service)
            if not tariff:
                if departure:
                    warnings.append(f"Не найдена ставка {service} для {departure}.")
                continue
            # Both КЕРОСИН and ЗАПРАВКА ВС use the fuel-tonnage volume in
            # НО rows 3–4 (and the analogous tech-stop rows 30–31).
            volume = fuel_tons
            amount = float(tariff["rate"]) * volume
            fuel += amount
            fuel_detail.append({"service": service, "rate": tariff["rate"], "volume": volume, "amount": amount})

    ground, ground_detail = calculate_ground(state, leg, tariff_index, line_type, is_techstop)

    ano_tariff = first_rate(tariff_index, departure, "АНО АД")
    aircraft_multiplier = float(state.get("aircraft_multipliers", {}).get(leg.aircraft, 0.0))
    ano = float(ano_tariff["rate"]) * aircraft_multiplier + distance / 100 * 1666.6 if ano_tariff and route else 0.0
    if not ano_tariff and departure:
        warnings.append(f"Не найдена ставка АНО АД для {departure}; компонент АНО принят равным 0.")
    if leg.aircraft not in state.get("aircraft_multipliers", {}):
        warnings.append(f"Для типа ВС {leg.aircraft} отсутствует коэффициент из Справочников.")

    catering = 0.0 if not route_key or route_key == "-" else 6 * 1500
    if catering and request.settings.catering:
        catering += leg.passengers * 500

    vat = (fuel + ground + ano + catering) * 0.1 if line_type == "ВВЛ" and {departure, arrival}.intersection({"DME", "SVO", "VKO"}) else 0.0

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
        # This is removed before returning API output. Excel's bottom line sums
        # full-precision row formulas and only then formats the result.
        "_raw_totals": raw_totals,
        "details": {"fuel": fuel_detail, "ground": ground_detail},
        "warnings": warnings,
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
    return {
        "calculated_at": datetime.now(timezone.utc).isoformat(),
        "legs": legs,
        "total": total,
        "warnings": list(dict.fromkeys(warnings)),
        "data_snapshot": {
            "revision": int(state.get("data_revision", 0)),
            "tariffs": len(state.get("imported_tariffs", [])),
            "manual_tariffs": len(state.get("manual_tariffs", [])),
            "fuel_prices": len(state.get("fuel_prices", [])),
            "routes": len(state.get("routes", [])),
        },
    }
