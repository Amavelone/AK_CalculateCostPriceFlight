from .validation import validate_configuration

BASELINE_CONFIGURATION = validate_configuration(
    {
        "schema_version": "1.0",
        "fuel": {"consumption_tons_per_hour": 2.7},
        "ano": {"route_rate_per_100_km": 1666.6},
        "catering": {"base_units": 6, "base_unit_rate": 1500, "passenger_surcharge": 500},
        "vat": {"rate": 0.1, "airports": ["DME", "SVO", "VKO"]},
        "ground": {
            "split_divisor": 2,
            "stairs_units": 2,
            "telebridge_minutes": 90,
            "transport_passenger_block": 100,
            "fire_truck_rate": 25132,
        },
        "initial_data": {
            "aircraft_multipliers": {"733": 1.0, "737": 1.0, "738": 1.0},
            "scenario_rates": {
                "ГБ 2026": {
                    "733": [78.48, 220.45, 272.17],
                    "737": [120.0, 280.0, 340.0],
                    "738": [165.73, 341.48, 391.28],
                },
                "Оперативная 2026": {
                    "733": [78.48, 220.45, 272.17],
                    "737": [120.0, 280.0, 340.0],
                    "738": [165.73, 341.48, 391.28],
                },
            },
        },
        "source_bindings": [
            {
                "id": "srv",
                "label": "Тарифы SRV",
                "description": "Тарифы услуг аэропортов",
                "parser": "srv_tariffs",
                "default_mask": "7480_srv*.xlsx",
            },
            {
                "id": "fuel_registry",
                "label": "Реестр керосина",
                "description": "Выгрузка 1С цен поставщиков",
                "parser": "fuel_registry",
                "default_mask": "реестр*.xlsx",
            },
            {
                "id": "monitor_workbook",
                "label": "Рабочая книга монитора",
                "description": "Маршруты, признак МВЛ и исходные параметры",
                "parser": "monitor_workbook",
                "default_mask": "Расчет себестоимости рейсов*.xlsx",
            },
        ],
    }
)

__all__ = ["BASELINE_CONFIGURATION"]
