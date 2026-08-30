from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Содержит пути среды выполнения с поддержкой переменных окружения.

    Явно заданные переменные окружения имеют приоритет над локальными
    значениями по умолчанию, чтобы конфигурация подходила для разных сред.
    """

    project_root: Path
    data_dir: Path
    default_source_dir: Path

    @classmethod
    def from_environment(cls) -> "Settings":
        project_root = Path(__file__).resolve().parents[3]
        data_dir = Path(os.getenv("MONITOR_DATA_DIRECTORY", project_root / "backend" / "data"))
        configured_source_dir = os.getenv("MONITOR_SOURCE_DIRECTORY")

        if configured_source_dir:
            default_source_dir = Path(configured_source_dir)
        else:
            local_downloads = Path("C:/Users/soale/Downloads")
            default_source_dir = local_downloads if local_downloads.exists() else data_dir / "sources"

        return cls(
            project_root=project_root,
            data_dir=data_dir,
            default_source_dir=default_source_dir,
        )


settings = Settings.from_environment()
