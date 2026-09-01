from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from .configuration.schema import CostMonitorConfiguration
from .reference_data.schema import CostMonitorReferenceData


class LegInput(BaseModel):
    id: str
    departure: str = ""
    arrival: str = ""
    aircraft: str = "738"
    passengers: int = Field(default=0, ge=0, le=1000)

    @field_validator("departure", "arrival", "aircraft")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()


class CalculationSettings(BaseModel):
    scenario: str = "ГБ 2026"
    fuel_source: Literal["ЦРТ", "АК"] = "ЦРТ"
    techstop_leg_id: str | None = None
    # Соответствует исходному значению AA2 текущей книги: фиксированная стоимость
    # питания присутствует всегда, а этот флаг включает доплату за пассажиров.
    catering: bool = False
    show_details: bool = True


class CalculationRequest(BaseModel):
    legs: list[LegInput] = Field(default_factory=list)
    settings: CalculationSettings = Field(default_factory=CalculationSettings)


class SourceConfigUpdate(BaseModel):
    directory: str = Field(min_length=1, max_length=600)
    mask: str = Field(min_length=1, max_length=120)


class SourceConfigResponse(BaseModel):
    id: Literal["srv", "fuel_registry"]
    label: str
    description: str
    directory: str
    mask: str
    parser: Literal["srv_tariffs", "fuel_registry"]
    last_status: Literal["not_updated", "uploaded", "ready", "error"]
    last_file: str | None = None
    active_file: str | None = None
    uploaded_file: str | None = None
    last_updated: str | None = None
    last_error: str | None = None
    last_note: str | None = None
    rows_read: int = 0
    rows_loaded: int = 0
    preview: list[dict[str, Any]] = Field(default_factory=list)


class SourcePreviewResponse(BaseModel):
    source: SourceConfigResponse
    preview: list[dict[str, Any]]


class SourceRawPreviewResponse(BaseModel):
    file: str
    sheet: str
    sheets: list[str]
    preview: list[dict[str, Any]]


class SourceRefreshAllResponse(BaseModel):
    sources: list[SourceConfigResponse]


class ReadinessCheckResponse(BaseModel):
    status: Literal["ok", "failed"]
    detail: str


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: dict[str, ReadinessCheckResponse]
    config_version: int | None = None
    reference_version: int | None = None
    data_revision: int | None = None


class ManualTariffInput(BaseModel):
    airport: str = Field(min_length=3, max_length=3)
    service: str = Field(min_length=1, max_length=100)
    rate: float = Field(ge=0)
    unit: str = Field(default="РУБ-ЕД", max_length=40)
    aircraft: str = Field(default="", max_length=20)
    note: str = Field(default="", max_length=500)

    @field_validator("airport", "aircraft")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("service", "unit", "note")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return value.strip()


class DraftPayload(BaseModel):
    calculation: CalculationRequest


class ConfigurationDraftUpdate(BaseModel):
    configuration: CostMonitorConfiguration


class ConfigurationDraftCreate(BaseModel):
    base: Literal["default", "active"] = "active"


class BusinessConfigurationDraftUpdate(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)
    flight_hour: dict[str, Any] | None = None


class ReferenceDataDraftUpdate(BaseModel):
    reference_data: CostMonitorReferenceData


class ConfigurationVersionResponse(BaseModel):
    version: int
    state: Literal["active", "inactive"]
    created_at: str
    activated_at: str | None
    validation_status: Literal["valid"]
    is_default: bool = False
    configuration: CostMonitorConfiguration | None = None


class ConfigurationDraftResponse(BaseModel):
    version: int
    state: Literal["draft"]
    base_version: int
    created_at: str
    updated_at: str
    validation_status: Literal["valid"]
    validated_at: str | None = None
    configuration: CostMonitorConfiguration


class ReferenceDataVersionResponse(BaseModel):
    version: int
    state: Literal["active", "inactive"]
    created_at: str
    activated_at: str | None
    validation_status: Literal["valid"]
    reference_data: CostMonitorReferenceData | None = None


class ReferenceDataDraftResponse(BaseModel):
    version: int
    state: Literal["draft"]
    base_version: int
    created_at: str
    updated_at: str
    validation_status: Literal["valid"]
    validated_at: str | None = None
    reference_data: CostMonitorReferenceData


class ConfigurationComparisonChange(BaseModel):
    path: str
    before: Any
    after: Any
    kind: Literal[
        "parameter_changed",
        "operation_added",
        "operation_removed",
        "operation_changed",
        "operation_reordered",
        "override_changed",
    ]
    summary: str
    presentation: dict[str, Any] | None = None


class ConfigurationReferenceResponse(BaseModel):
    version: int
    state: Literal["active", "inactive", "draft"]
    created_at: str
    activated_at: str | None = None
    updated_at: str | None = None
    base_version: int | None = None
    validation_status: Literal["valid"]
    is_default: bool = False


class ConfigurationCompareResponse(BaseModel):
    left: ConfigurationReferenceResponse
    right: ConfigurationReferenceResponse
    changes: list[ConfigurationComparisonChange]


class ReferenceDataComparisonChange(BaseModel):
    path: str
    before: Any
    after: Any
    kind: Literal["record_added", "record_removed", "record_changed"]
    summary: str


class ReferenceDataCompareResponse(BaseModel):
    left: ConfigurationReferenceResponse
    right: ConfigurationReferenceResponse
    changes: list[ReferenceDataComparisonChange]


class DetailRow(BaseModel):
    airport: str
    service: str
    rate: float
    volume: float
    divisor: float = 1
    amount: float


class CalculationDiagnostics(BaseModel):
    """Машиночитаемое описание degraded calculation без изменения чисел."""

    code: str
    severity: Literal["warning"] = "warning"
    component: str
    reference: str | None = None
    message: str


class CalculationDetails(BaseModel):
    fuel: list[DetailRow]
    ground: list[DetailRow]
    ano: list[DetailRow]
    catering: list[DetailRow]
    vat: list[DetailRow]


class CalculationLegResponse(BaseModel):
    id: str
    route: str
    departure: str
    arrival: str
    aircraft: str
    passengers: int
    flight_time: float
    distance: float
    fuel_tons: float
    line_type: str
    is_techstop: bool
    components: dict[str, float]
    totals: dict[str, float]
    details: CalculationDetails
    warnings: list[str]
    status: Literal["complete", "degraded"]
    diagnostics: list[CalculationDiagnostics]


class DataSnapshotResponse(BaseModel):
    revision: int
    tariffs: int
    manual_tariffs: int
    fuel_prices: int
    routes: int
    reference_version: int


class CalculationTraceStep(BaseModel):
    stage: Literal["input", "lookup", "parameters", "operation", "result"]
    component: str
    operation: str | None = None
    values: dict[str, Any]


class CalculationTraceLeg(BaseModel):
    leg_id: str
    steps: list[CalculationTraceStep]


class CalculationTrace(BaseModel):
    config_version: int
    configuration_state: Literal["active", "draft"]
    data_revision: int
    reference_version: int
    reference_state: Literal["active", "draft"]
    legs: list[CalculationTraceLeg]


class CalculationResponse(BaseModel):
    calculated_at: str
    legs: list[CalculationLegResponse]
    total: dict[str, float]
    warnings: list[str]
    status: Literal["complete", "degraded"]
    diagnostics: list[CalculationDiagnostics]
    data_snapshot: DataSnapshotResponse
    config_version: int
    configuration_state: Literal["active", "draft"]
    reference_version: int
    reference_state: Literal["active", "draft"]
    trace: CalculationTrace


class ConfigurationCapabilityItem(BaseModel):
    name: str
    value_type: str | None = None
    description: str
    arguments: list[str] = Field(default_factory=list)


class ConfigurationCapabilitiesResponse(BaseModel):
    schema_version: Literal["2.0"]
    parameters: list[str]
    variables: list[ConfigurationCapabilityItem]
    operations: list[ConfigurationCapabilityItem]
    lookups: list[ConfigurationCapabilityItem]
    condition_operators: list[str]


class CalculationDifference(BaseModel):
    total: dict[str, float]
    legs: dict[str, dict[str, float]]


class ConfigurationPreviewComparisonResponse(BaseModel):
    active: CalculationResponse
    draft: CalculationResponse
    difference: CalculationDifference
