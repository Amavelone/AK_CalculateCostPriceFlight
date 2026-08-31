from __future__ import annotations

import copy
import uuid
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, File, HTTPException, Request, Response, UploadFile

from ...core.config import settings
from .calculation import calculate
from .catalog import tariffs_for_view
from .configuration import (
    ConfigurationConflictError,
    ConfigurationNotFoundError,
    ConfigurationService,
    ConfigurationValidationError,
    JsonConfigurationRepository,
)
from .exports import build_export_snapshot, export_filename, json_bytes, xlsx_bytes
from .records import CostMonitorDataset
from .repository import CostMonitorRepository
from .schemas import (
    CalculationRequest,
    CalculationResponse,
    ConfigurationCompareResponse,
    ConfigurationDraftResponse,
    ConfigurationDraftUpdate,
    ConfigurationVersionResponse,
    DraftPayload,
    ManualTariffInput,
    SourceConfigUpdate,
)
from .sources import (
    activate_staged_source,
    find_active_file,
    mark_source_error,
    refresh_source,
    save_uploaded_file,
    source_by_id,
    stage_source_refresh,
    workbook_preview,
)
from .store import JsonStore, utc_now

router = APIRouter()
repository: CostMonitorRepository = JsonStore(settings)
configuration_service = ConfigurationService(JsonConfigurationRepository(repository))
COOKIE_NAME = "cost_monitor_draft"


def default_calculation() -> dict[str, Any]:
    return {
        "legs": [{"id": "leg-1", "departure": "", "arrival": "", "aircraft": "738", "passengers": 0}],
        "settings": {
            "scenario": "ГБ 2026",
            "fuel_source": "ЦРТ",
            "techstop_leg_id": None,
            "catering": False,
            "show_details": True,
        },
    }


def draft_id(request: Request, response: Response) -> str:
    value = request.cookies.get(COOKIE_NAME)
    if value:
        return value
    value = uuid.uuid4().hex
    response.set_cookie(
        key=COOKIE_NAME,
        value=value,
        max_age=60 * 60 * 24 * 180,
        httponly=True,
        samesite="lax",
        secure=False,  # Local development. Enable HTTPS + Secure in deployment.
    )
    return value


def get_source_or_404(state: dict[str, Any], source_id: str) -> dict[str, Any]:
    try:
        return source_by_id(state, source_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Источник не найден") from error


def configuration_error_to_http(error: Exception) -> HTTPException:
    if isinstance(error, ConfigurationNotFoundError):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, ConfigurationConflictError):
        return HTTPException(status_code=409, detail=str(error))
    if isinstance(error, ConfigurationValidationError):
        return HTTPException(status_code=422, detail=str(error))
    return HTTPException(status_code=500, detail="Не удалось обработать configuration")


@router.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/dashboard")
def dashboard() -> dict[str, Any]:
    state = repository.read()
    return {
        "sources": state["source_configs"],
        "stats": {
            "tariffs": len(state["imported_tariffs"]),
            "manual_tariffs": len(state["manual_tariffs"]),
            "fuel_prices": len(state["fuel_prices"]),
            "routes": len(state["routes"]),
        },
        "data_revision": state.get("data_revision", 0),
        "data_updated_at": state.get("data_updated_at"),
    }


@router.get("/api/calculation-options")
def calculation_options() -> dict[str, list[str]]:
    """Возвращает интерфейсу активные сценарии и типы воздушных судов.

    Набор строится из текущего состояния книги и дополняется базовыми типами,
    поэтому сохранённый черновик остаётся доступным после обновления данных.
    """

    state = repository.read()
    aircraft = {"733", "737", "738"}
    aircraft.update(state.get("aircraft_multipliers", {}).keys())
    for rates in state.get("scenario_rates", {}).values():
        aircraft.update(rates.keys())
    return {
        "scenarios": list(state.get("scenario_rates", {}).keys()) or ["ГБ 2026"],
        "aircraft": sorted(aircraft),
    }


@router.get("/api/drafts/current")
def get_current_draft(request: Request, response: Response) -> dict[str, Any]:
    key = draft_id(request, response)
    state = repository.read()
    saved = state["drafts"].get(key)
    return saved or {"calculation": default_calculation(), "updated_at": None}


@router.put("/api/drafts/current")
def save_current_draft(payload: DraftPayload, request: Request, response: Response) -> dict[str, Any]:
    key = draft_id(request, response)

    def operation(state: dict[str, Any]) -> dict[str, Any]:
        draft = {"calculation": payload.calculation.model_dump(), "updated_at": utc_now()}
        state["drafts"][key] = draft
        return draft

    return repository.mutate(operation)


@router.post("/api/calculations", response_model=CalculationResponse)
def calculate_cost(payload: CalculationRequest) -> dict[str, Any]:
    active = configuration_service.active()
    return calculate(CostMonitorDataset.from_state(repository.read()), payload, active["configuration"], active["version"], active["state"])


@router.post("/api/exports/{file_format}")
def export_calculation(file_format: str, payload: CalculationRequest) -> Response:
    """Формирует JSON или XLSX из одного завершённого снимка расчёта.

    Оба формата получают одинаковые входы, компоненты и итоги; экспорт не
    запускает альтернативную ветку бизнес-расчёта.
    """

    if file_format not in {"json", "xlsx"}:
        raise HTTPException(status_code=404, detail="Формат выгрузки не поддерживается")
    active = configuration_service.active()
    result = calculate(CostMonitorDataset.from_state(repository.read()), payload, active["configuration"], active["version"], active["state"])
    snapshot = build_export_snapshot(payload, result)
    content = json_bytes(snapshot) if file_format == "json" else xlsx_bytes(snapshot)
    media_type = "application/json; charset=utf-8" if file_format == "json" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    filename = export_filename(snapshot, file_format)
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.get("/api/configuration/active", response_model=ConfigurationVersionResponse)
def active_configuration() -> dict[str, Any]:
    try:
        active = configuration_service.active()
        active["configuration"] = active["configuration"].model_dump(mode="json")
        return active
    except Exception as error:
        raise configuration_error_to_http(error) from error


@router.get("/api/configuration/versions", response_model=list[ConfigurationVersionResponse])
def list_configuration_versions() -> list[dict[str, Any]]:
    try:
        return configuration_service.list_versions()
    except Exception as error:
        raise configuration_error_to_http(error) from error


@router.post("/api/configuration/drafts", response_model=ConfigurationDraftResponse, status_code=201)
def create_configuration_draft() -> dict[str, Any]:
    try:
        return configuration_service.create_draft()
    except Exception as error:
        raise configuration_error_to_http(error) from error


@router.put("/api/configuration/drafts/{version}", response_model=ConfigurationDraftResponse)
def update_configuration_draft(version: int, payload: ConfigurationDraftUpdate) -> dict[str, Any]:
    try:
        return configuration_service.update_draft(version, payload.configuration.model_dump(mode="json"))
    except Exception as error:
        raise configuration_error_to_http(error) from error


@router.post("/api/configuration/drafts/{version}/validate", response_model=ConfigurationDraftResponse)
def validate_configuration_draft(version: int) -> dict[str, Any]:
    try:
        return configuration_service.validate_draft(version)
    except Exception as error:
        raise configuration_error_to_http(error) from error


@router.get("/api/configuration/compare/{left_version}/{right_version}", response_model=ConfigurationCompareResponse)
def compare_configuration_versions(left_version: int, right_version: int) -> dict[str, Any]:
    try:
        return configuration_service.compare(left_version, right_version)
    except Exception as error:
        raise configuration_error_to_http(error) from error


@router.post("/api/configuration/drafts/{version}/preview", response_model=CalculationResponse)
def preview_configuration_draft(version: int, payload: CalculationRequest) -> dict[str, Any]:
    try:
        configuration = configuration_service.draft_configuration(version)
        return calculate(CostMonitorDataset.from_state(repository.read()), payload, configuration, version, "draft")
    except Exception as error:
        raise configuration_error_to_http(error) from error


@router.post("/api/configuration/drafts/{version}/activate", response_model=ConfigurationVersionResponse)
def activate_configuration_draft(version: int) -> dict[str, Any]:
    try:
        return configuration_service.activate(version)
    except Exception as error:
        raise configuration_error_to_http(error) from error


@router.post("/api/configuration/rollback/{version}", response_model=ConfigurationVersionResponse)
def rollback_configuration(version: int) -> dict[str, Any]:
    try:
        return configuration_service.rollback(version)
    except Exception as error:
        raise configuration_error_to_http(error) from error


@router.get("/api/sources")
def list_sources() -> list[dict[str, Any]]:
    return repository.read()["source_configs"]


@router.put("/api/sources/{source_id}")
def update_source(source_id: str, payload: SourceConfigUpdate) -> dict[str, Any]:
    def operation(state: dict[str, Any]) -> dict[str, Any]:
        source = get_source_or_404(state, source_id)
        source["directory"] = payload.directory.strip()
        source["mask"] = payload.mask.strip()
        source["last_status"] = "not_updated"
        source["last_error"] = None
        repository.append_audit(state, "source_config_updated", source_id)
        return source

    return repository.mutate(operation)


@router.get("/api/sources/{source_id}/preview")
def source_preview(source_id: str) -> dict[str, Any]:
    state = repository.read()
    source = get_source_or_404(state, source_id)
    return {"source": source, "preview": source.get("preview", [])}


@router.get("/api/sources/{source_id}/raw-preview")
def source_raw_preview(source_id: str, sheet: str | None = None) -> dict[str, Any]:
    state = repository.read()
    source = get_source_or_404(state, source_id)
    try:
        file_path = find_active_file(source)
        return {"file": file_path.name, **workbook_preview(file_path, sheet_name=sheet)}
    except Exception as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/api/sources/{source_id}/refresh")
def refresh_one_source(source_id: str) -> dict[str, Any]:
    def operation(state: dict[str, Any]) -> dict[str, Any]:
        get_source_or_404(state, source_id)
        try:
            source = refresh_source(state, source_id, utc_now())
            repository.mark_calculation_data_changed(state)
            repository.append_audit(state, "source_refreshed", source_id)
            return source
        except Exception as error:
            source = mark_source_error(state, source_id, str(error), utc_now())
            repository.append_audit(state, "source_refresh_failed", f"{source_id}: {error}")
            return source

    return repository.mutate(operation)


@router.post("/api/sources/refresh-all")
def refresh_all_sources() -> dict[str, Any]:
    def operation(state: dict[str, Any]) -> dict[str, Any]:
        staged = []
        failures: dict[str, str] = {}
        candidate = copy.deepcopy(state)
        for config in state["source_configs"]:
            source_id = config["id"]
            try:
                staged.append(stage_source_refresh(candidate, source_id, utc_now()))
            except Exception as error:
                failures[source_id] = str(error)
                repository.append_audit(state, "source_refresh_failed", f"{source_id}: {error}")
        if failures:
            for source_id, message in failures.items():
                mark_source_error(state, source_id, message, utc_now())
            repository.append_audit(state, "all_sources_refresh_failed", "active dataset preserved")
            return {"sources": state["source_configs"]}
        for item in staged:
            activate_staged_source(state, item)
        if staged:
            repository.mark_calculation_data_changed(state)
        repository.append_audit(state, "all_sources_refreshed", f"{len(staged)} источника(ов)")
        return {"sources": state["source_configs"]}

    return repository.mutate(operation)


@router.post("/api/sources/{source_id}/upload")
async def upload_source_file(source_id: str, file: UploadFile = File(...)) -> dict[str, Any]:
    def operation(state: dict[str, Any]) -> dict[str, Any]:
        source = get_source_or_404(state, source_id)
        target = save_uploaded_file(source, file.filename or "source.xlsx", file.file)
        source.update(
            {
                "last_status": "uploaded",
                "uploaded_file": target.name,
                "last_error": None,
                "last_note": "Файл загружен. Запустите обновление для парсинга.",
            }
        )
        repository.append_audit(state, "source_uploaded", f"{source_id}: {target.name}")
        return source

    try:
        return repository.mutate(operation)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/api/tariffs")
def list_tariffs(search: str = "") -> list[dict[str, Any]]:
    tariffs = tariffs_for_view(repository.read())
    phrase = search.strip().upper()
    if not phrase:
        return tariffs
    return [
        tariff
        for tariff in tariffs
        if phrase in tariff["airport"].upper() or phrase in tariff["service"].upper()
    ]


@router.post("/api/tariffs/manual", status_code=201)
def add_manual_tariff(payload: ManualTariffInput) -> dict[str, Any]:
    def operation(state: dict[str, Any]) -> dict[str, Any]:
        airport = payload.airport.upper()
        service = payload.service.strip().upper()
        key = f"{airport}-{service}"
        existing = tariffs_for_view(state)
        if any(f"{item['airport']}-{item['service']}" == key for item in existing):
            raise ValueError("Такой ключ уже есть в справочнике. Ручное дополнение не является override.")
        tariff = {
            "id": f"manual-{uuid.uuid4().hex}",
            "airport": airport,
            "service": service,
            "rate": payload.rate,
            "unit": payload.unit.strip(),
            "aircraft": payload.aircraft.strip().upper(),
            "start_date": "",
            "end_date": "",
            "organization": "",
            "note": payload.note.strip(),
            "source": "manual",
            "source_file": None,
            "source_row": None,
        }
        state["manual_tariffs"].append(tariff)
        repository.mark_calculation_data_changed(state)
        repository.append_audit(state, "manual_tariff_added", key)
        return tariff

    try:
        return repository.mutate(operation)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.delete("/api/tariffs/manual/{tariff_id}", status_code=204)
def delete_manual_tariff(tariff_id: str) -> Response:
    def operation(state: dict[str, Any]) -> bool:
        initial = len(state["manual_tariffs"])
        state["manual_tariffs"] = [item for item in state["manual_tariffs"] if item["id"] != tariff_id]
        if len(state["manual_tariffs"]) == initial:
            return False
        repository.mark_calculation_data_changed(state)
        repository.append_audit(state, "manual_tariff_deleted", tariff_id)
        return True

    if not repository.mutate(operation):
        raise HTTPException(status_code=404, detail="Ручная запись не найдена")
    return Response(status_code=204)


@router.get("/api/routes")
def list_routes(query: str = "") -> list[dict[str, Any]]:
    routes = repository.read()["routes"]
    phrase = query.strip().upper()
    filtered = [route for route in routes if not phrase or phrase in route["key"]]
    return filtered[:50]


@router.get("/api/audit")
def audit_log() -> list[dict[str, Any]]:
    return list(reversed(repository.read().get("audit_log", [])))
