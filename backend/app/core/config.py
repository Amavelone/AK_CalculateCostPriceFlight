from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Явные runtime-настройки с безопасными repository-local значениями для разработки."""

    project_root: Path
    data_dir: Path
    default_source_dir: Path
    app_env: str = "development"
    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "INFO"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @classmethod
    def from_environment(cls) -> Settings:
        project_root = Path(__file__).resolve().parents[3]
        app_env = os.getenv("APP_ENV", "development").strip().lower()
        if app_env not in {"development", "production"}:
            raise ValueError("APP_ENV must be development or production")

        required = ("MONITOR_DATA_DIRECTORY", "MONITOR_SOURCE_DIRECTORY", "HOST", "PORT", "LOG_LEVEL")
        if app_env == "production":
            missing = [name for name in required if not os.getenv(name, "").strip()]
            if missing:
                raise ValueError(f"Production requires explicit settings: {', '.join(missing)}")

        data_dir = Path(os.getenv("MONITOR_DATA_DIRECTORY", project_root / "backend" / "data"))
        default_source_dir = Path(os.getenv("MONITOR_SOURCE_DIRECTORY", data_dir / "sources"))
        host = os.getenv("HOST", "127.0.0.1").strip()
        log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
        if not host:
            raise ValueError("HOST must not be blank")
        if log_level not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}:
            raise ValueError("LOG_LEVEL must be CRITICAL, ERROR, WARNING, INFO, or DEBUG")
        try:
            port = int(os.getenv("PORT", "8000"))
        except ValueError as error:
            raise ValueError("PORT must be an integer") from error
        if not 1 <= port <= 65535:
            raise ValueError("PORT must be between 1 and 65535")

        if app_env == "production":
            for name, path in (("MONITOR_DATA_DIRECTORY", data_dir), ("MONITOR_SOURCE_DIRECTORY", default_source_dir)):
                if not path.is_absolute():
                    raise ValueError(f"{name} must be an absolute path in production")
                if not path.is_dir():
                    raise ValueError(f"{name} must be an existing directory")
            if not os.access(data_dir, os.R_OK | os.W_OK):
                raise ValueError("MONITOR_DATA_DIRECTORY must be readable and writable")
            if not os.access(default_source_dir, os.R_OK | os.W_OK):
                raise ValueError("MONITOR_SOURCE_DIRECTORY must be readable and writable")

        return cls(
            project_root=project_root,
            data_dir=data_dir,
            default_source_dir=default_source_dir,
            app_env=app_env,
            host=host,
            port=port,
            log_level=log_level,
        )


def configure_logging(runtime_settings: Settings) -> None:
    """Настраивает компактные текстовые логи без секретов и payload'ов запросов."""

    logging.basicConfig(
        level=getattr(logging, runtime_settings.log_level),
        format="timestamp=%(asctime)s level=%(levelname)s logger=%(name)s message=%(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )


settings = Settings.from_environment()
