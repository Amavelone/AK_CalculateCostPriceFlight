from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from ..records import CostMonitorDataset, TariffRecord
from .schema import CostMonitorConfiguration

ValueOrigin = Literal["baseline_configuration", "runtime_configuration", "source", "admin_override"]


@dataclass(frozen=True)
class EffectiveValue:
    value: Any
    origin: ValueOrigin
    base_value: Any | None = None
    reference: str | None = None

    def trace(self) -> dict[str, Any]:
        result = {"value": self.value, "origin": self.origin}
        if self.base_value is not None:
            result["base_value"] = self.base_value
        if self.reference is not None:
            result["reference"] = self.reference
        return result


@dataclass(frozen=True)
class EffectiveCalculationContext:
    dataset: CostMonitorDataset
    configuration: CostMonitorConfiguration
    config_version: int
    configuration_state: str
    tariff_index: dict[str, TariffRecord]

    @property
    def configuration_origin(self) -> ValueOrigin:
        return "baseline_configuration" if self.config_version == 1 else "runtime_configuration"

    def airport_tariff(self, airport: str, service: str) -> EffectiveValue:
        tariff = self.tariff_index.get(f"{airport}-{service}")
        return EffectiveValue(
            tariff.rate if tariff else 0.0,
            "source",
            reference=f"{airport}-{service}",
        )

    def aircraft_multiplier(self, aircraft: str) -> EffectiveValue:
        base = self.dataset.aircraft_multipliers.get(aircraft)
        overrides = self.configuration.overrides.aircraft_multipliers
        if aircraft in overrides:
            return EffectiveValue(
                float(overrides[aircraft]),
                "admin_override",
                float(base) if base is not None else None,
                aircraft,
            )
        return EffectiveValue(float(base or 0.0), "source", reference=aircraft)

    def scenario_rate(self, scenario: str, aircraft: str, level: int) -> EffectiveValue:
        source_rates = self.dataset.scenario_rates.get(scenario, {}).get(aircraft)
        override_rates = self.configuration.overrides.scenario_rates.get(scenario, {}).get(aircraft)
        if override_rates is not None:
            return EffectiveValue(
                float(override_rates[level]),
                "admin_override",
                float(source_rates[level]) if source_rates is not None else None,
                f"{scenario}/{aircraft}/m{level + 1}",
            )
        return EffectiveValue(
            float(source_rates[level]) if source_rates is not None else 0.0,
            "source",
            reference=f"{scenario}/{aircraft}/m{level + 1}",
        )


__all__ = ["EffectiveCalculationContext", "EffectiveValue", "ValueOrigin"]
