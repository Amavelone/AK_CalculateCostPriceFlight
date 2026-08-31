"""Production-парсеры внешних источников Cost Monitor."""

from .fuel import fetch_usd_rate, parse_fuel_registry
from .tariffs import parse_srv_tariffs

__all__ = [
    "fetch_usd_rate",
    "parse_fuel_registry",
    "parse_srv_tariffs",
]
