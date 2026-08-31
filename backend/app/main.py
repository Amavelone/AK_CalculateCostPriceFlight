from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .core.config import settings
from .modules.cost_monitor.api import router as cost_monitor_router

app = FastAPI(
    title="Монитор расчета себестоимости",
    version="0.1.0",
    description="API модульного монитора себестоимости рейсов.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(cost_monitor_router)

frontend_dist = settings.project_root / "frontend" / "dist"


@app.get("/admin", include_in_schema=False)
def admin_ui() -> FileResponse:
    index = frontend_dist / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="Frontend build не найден; используйте Vite /admin")
    return FileResponse(index)


if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
