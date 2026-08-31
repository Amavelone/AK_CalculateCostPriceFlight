from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .parsers import parse_fuel_registry, parse_srv_tariffs
from .records import CostMonitorDataset, FuelPriceRecord, MonitorWorkbookData, TariffRecord


class SourceData(Protocol):
    """Typed canonical payload produced by one module-owned physical adapter."""

    def apply(self, dataset: CostMonitorDataset) -> CostMonitorDataset: ...

    @property
    def rows_loaded(self) -> int: ...


@dataclass(frozen=True)
class SrvTariffData:
    tariffs: tuple[TariffRecord, ...]

    def apply(self, dataset: CostMonitorDataset) -> CostMonitorDataset:
        return dataset.with_srv_tariffs(self.tariffs)

    @property
    def rows_loaded(self) -> int:
        return len(self.tariffs)


@dataclass(frozen=True)
class FuelRegistryData:
    prices: tuple[FuelPriceRecord, ...]

    def apply(self, dataset: CostMonitorDataset) -> CostMonitorDataset:
        return dataset.with_fuel_prices(self.prices)

    @property
    def rows_loaded(self) -> int:
        return len(self.prices)


@dataclass(frozen=True)
class MonitorWorkbookSourceData:
    workbook: MonitorWorkbookData

    def apply(self, dataset: CostMonitorDataset) -> CostMonitorDataset:
        return dataset.with_monitor_workbook(self.workbook)

    @property
    def rows_loaded(self) -> int:
        return len(self.workbook.routes)


@dataclass(frozen=True)
class SourceRunResult:
    """Normalized candidate ready for lifecycle validation and atomic activation."""

    source_id: str
    data: SourceData
    rows_read: int
    preview: list[dict[str, Any]]
    note: str | None


class SourceAdapter(Protocol):
    """Physical-source adapter contract; SQL adapters can implement it later."""

    source_id: str
    parser_id: str

    def load(self, path: Path) -> SourceRunResult: ...


@dataclass(frozen=True)
class SrvTariffsAdapter:
    source_id: str = "srv"
    parser_id: str = "srv_tariffs"

    def load(self, path: Path) -> SourceRunResult:
        tariffs, rows_read, preview, note = parse_srv_tariffs(path)
        return SourceRunResult(
            source_id=self.source_id,
            data=SrvTariffData(tuple(TariffRecord.from_mapping(item) for item in tariffs)),
            rows_read=rows_read,
            preview=preview,
            note=note,
        )


@dataclass(frozen=True)
class FuelRegistryAdapter:
    source_id: str = "fuel_registry"
    parser_id: str = "fuel_registry"

    def load(self, path: Path) -> SourceRunResult:
        prices, rows_read, preview, note = parse_fuel_registry(path)
        return SourceRunResult(
            source_id=self.source_id,
            data=FuelRegistryData(tuple(FuelPriceRecord.from_mapping(item) for item in prices)),
            rows_read=rows_read,
            preview=preview,
            note=note,
        )


@dataclass(frozen=True)
class MonitorWorkbookAdapter:
    """DEV compatibility adapter; its parser is imported only when explicitly used."""

    source_id: str = "monitor_workbook"
    parser_id: str = "monitor_workbook"

    def load(self, path: Path) -> SourceRunResult:
        from .parsers.monitor import parse_monitor_workbook

        result, rows_read, preview, note = parse_monitor_workbook(path)
        return SourceRunResult(
            source_id=self.source_id,
            data=MonitorWorkbookSourceData(MonitorWorkbookData.from_mapping(result)),
            rows_read=rows_read,
            preview=preview,
            note=note,
        )


PRODUCTION_ADAPTERS: tuple[SourceAdapter, ...] = (SrvTariffsAdapter(), FuelRegistryAdapter())
COMPATIBILITY_ADAPTERS: tuple[SourceAdapter, ...] = (MonitorWorkbookAdapter(),)
PRODUCTION_ADAPTERS_BY_PARSER: Mapping[str, SourceAdapter] = {
    adapter.parser_id: adapter for adapter in PRODUCTION_ADAPTERS
}
COMPATIBILITY_ADAPTERS_BY_PARSER: Mapping[str, SourceAdapter] = {
    adapter.parser_id: adapter for adapter in COMPATIBILITY_ADAPTERS
}


def production_adapter_for_parser(parser_id: str) -> SourceAdapter:
    try:
        return PRODUCTION_ADAPTERS_BY_PARSER[parser_id]
    except KeyError as error:
        raise ValueError(f"Не поддерживается production source adapter: {parser_id}") from error


def compatibility_adapter_for_parser(parser_id: str) -> SourceAdapter:
    try:
        return COMPATIBILITY_ADAPTERS_BY_PARSER[parser_id]
    except KeyError as error:
        raise ValueError(f"Не поддерживается compatibility source adapter: {parser_id}") from error
