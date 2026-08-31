from __future__ import annotations

import uvicorn

from .core.config import configure_logging, settings


def main() -> None:
    """Start one non-reloading worker for the JsonStore-backed runtime."""

    configure_logging(settings)
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=False, workers=1, log_config=None)


if __name__ == "__main__":
    main()
