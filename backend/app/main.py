from __future__ import annotations

import logging
import time

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .core.config import Settings, configure_logging, settings
from .core.release import APPLICATION_VERSION
from .modules.cost_monitor import api as cost_monitor_api

logger = logging.getLogger("cost_monitor.request")


def _runtime_versions() -> tuple[int | str, int | str, int | str]:
    """Best-effort log context: observability never changes endpoint behavior."""

    try:
        state = cost_monitor_api.repository.read()
        data_revision: int | str = int(state.get("data_revision", 0))
    except Exception:  # pragma: no cover - exercised through request middleware
        data_revision = "unavailable"
    try:
        config_version: int | str = int(cost_monitor_api.configuration_service.active()["version"])
    except Exception:  # pragma: no cover - exercised through request middleware
        config_version = "unavailable"
    try:
        reference_version: int | str = int(cost_monitor_api.reference_data_service.active()["version"])
    except Exception:  # pragma: no cover - exercised through request middleware
        reference_version = "unavailable"
    return config_version, reference_version, data_revision


def create_app(runtime_settings: Settings = settings) -> FastAPI:
    """Build the FastAPI application for an explicit runtime environment."""

    configure_logging(runtime_settings)
    application = FastAPI(
        title="Монитор расчета себестоимости",
        version=APPLICATION_VERSION,
        description="API модульного монитора себестоимости рейсов.",
    )
    if not runtime_settings.is_production:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    application.include_router(cost_monitor_api.router)
    frontend_dist = runtime_settings.project_root / "frontend" / "dist"

    @application.middleware("http")
    async def log_request(request, call_next):
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as error:
            config_version, reference_version, data_revision = _runtime_versions()
            logger.exception(
                "endpoint=%s status=500 error=%s config_version=%s reference_version=%s data_revision=%s duration_ms=%d",
                request.url.path,
                type(error).__name__,
                config_version,
                reference_version,
                data_revision,
                (time.perf_counter() - started) * 1000,
            )
            raise

        config_version, reference_version, data_revision = _runtime_versions()
        level = logging.ERROR if response.status_code >= 500 else logging.INFO
        error = f"http_{response.status_code}" if response.status_code >= 400 else "none"
        logger.log(
            level,
            "endpoint=%s status=%s error=%s config_version=%s reference_version=%s data_revision=%s duration_ms=%d",
            request.url.path,
            response.status_code,
            error,
            config_version,
            reference_version,
            data_revision,
            (time.perf_counter() - started) * 1000,
        )
        return response

    @application.get("/admin", include_in_schema=False)
    def admin_ui() -> FileResponse:
        index = frontend_dist / "index.html"
        if not index.exists():
            raise HTTPException(status_code=404, detail="Frontend build не найден; используйте Vite /admin")
        return FileResponse(index)

    if frontend_dist.exists():
        application.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
    return application


frontend_dist = settings.project_root / "frontend" / "dist"
app = create_app()
