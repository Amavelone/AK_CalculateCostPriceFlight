from __future__ import annotations

import copy
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import main
from app.core.config import Settings
from app.modules.cost_monitor import api as cost_api
from app.modules.cost_monitor.configuration import ConfigurationService, JsonConfigurationRepository
from app.modules.cost_monitor.reference_data import ReferenceDataService
from app.modules.cost_monitor.reference_data.repository import JsonReferenceDataRepository
from app.modules.cost_monitor.store import build_default_state
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import Response


class MemoryStore:
    def __init__(self, state: dict) -> None:
        self.state = copy.deepcopy(state)

    def read(self) -> dict:
        return copy.deepcopy(self.state)


class BrokenStore:
    def read(self) -> dict:
        raise OSError("store is unavailable")


def runtime_settings(app_env: str) -> Settings:
    root = Path(__file__).resolve().parents[2]
    return Settings(
        project_root=root,
        data_dir=root / "backend" / "data",
        default_source_dir=root / "backend" / "data" / "sources",
        app_env=app_env,
        host="127.0.0.1",
        port=8000,
        log_level="INFO",
    )


class SettingsTests(unittest.TestCase):
    def test_development_uses_repository_local_defaults_not_downloads(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            configured = Settings.from_environment()

        self.assertEqual(configured.app_env, "development")
        self.assertEqual(configured.data_dir, configured.project_root / "backend" / "data")
        self.assertEqual(configured.default_source_dir, configured.data_dir / "sources")
        self.assertNotIn("Downloads", str(configured.default_source_dir))

    def test_production_requires_explicit_existing_paths_and_runtime_settings(self) -> None:
        with patch.dict(os.environ, {"APP_ENV": "production"}, clear=True):
            with self.assertRaisesRegex(ValueError, "Production requires"):
                Settings.from_environment()

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            data_dir = root / "data"
            source_dir = root / "sources"
            data_dir.mkdir()
            source_dir.mkdir()
            environment = {
                "APP_ENV": "production",
                "MONITOR_DATA_DIRECTORY": str(data_dir),
                "MONITOR_SOURCE_DIRECTORY": str(source_dir),
                "HOST": "127.0.0.1",
                "PORT": "8010",
                "LOG_LEVEL": "warning",
            }
            with patch.dict(os.environ, environment, clear=True):
                configured = Settings.from_environment()

        self.assertTrue(configured.is_production)
        self.assertEqual(configured.port, 8010)
        self.assertEqual(configured.log_level, "WARNING")


class RuntimeHardeningTests(unittest.TestCase):
    def _ready_response(self, store: MemoryStore | BrokenStore) -> tuple[Response, dict]:
        configuration = ConfigurationService(JsonConfigurationRepository(store))
        reference = ReferenceDataService(JsonReferenceDataRepository(store))
        response = Response()
        with (
            patch.object(cost_api, "repository", store),
            patch.object(cost_api, "configuration_service", configuration),
            patch.object(cost_api, "reference_data_service", reference),
        ):
            payload = cost_api.readiness(response)
        return response, payload

    @staticmethod
    def _ready_state() -> dict:
        state = build_default_state(Path("sources"))
        for source in state["source_configs"]:
            source.update({"last_status": "ready", "active_file": f"{source['id']}.xlsx"})
        state["imported_tariffs"] = [{"airport": "AAA", "service": "ВОДА", "rate": 1}]
        state["fuel_prices"] = [{"airport": "AAA", "price": 1}]
        return state

    def test_readiness_is_strict_for_store_versions_and_production_sources(self) -> None:
        state = self._ready_state()
        response, payload = self._ready_response(MemoryStore(state))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["config_version"], 1)
        self.assertEqual(payload["reference_version"], 1)
        self.assertEqual(payload["checks"]["source:srv"]["status"], "ok")
        self.assertEqual(payload["checks"]["source:fuel_registry"]["status"], "ok")

        for source_id in ("srv", "fuel_registry"):
            degraded = self._ready_state()
            next(source for source in degraded["source_configs"] if source["id"] == source_id)["last_status"] = "error"
            response, payload = self._ready_response(MemoryStore(degraded))
            self.assertEqual(response.status_code, 503)
            self.assertEqual(payload["checks"][f"source:{source_id}"]["status"], "failed")

            missing = self._ready_state()
            missing["source_configs"] = [source for source in missing["source_configs"] if source["id"] != source_id]
            response, payload = self._ready_response(MemoryStore(missing))
            self.assertEqual(response.status_code, 503)
            self.assertEqual(payload["checks"][f"source:{source_id}"]["detail"], "missing configuration")

    def test_readiness_rejects_unreadable_or_invalid_active_state_and_ignores_workbook(self) -> None:
        response, payload = self._ready_response(BrokenStore())
        self.assertEqual(response.status_code, 503)
        self.assertEqual(payload["checks"]["store"]["status"], "failed")

        for key, check in (("active_configuration_version", "active_configuration"), ("active_reference_data_version", "active_reference_data")):
            invalid = self._ready_state()
            invalid.pop(key)
            response, payload = self._ready_response(MemoryStore(invalid))
            self.assertEqual(response.status_code, 503)
            self.assertEqual(payload["checks"][check]["status"], "failed")

        workbook_state = self._ready_state()
        workbook_state["source_configs"].append({"id": "monitor_workbook", "last_status": "error"})
        response, payload = self._ready_response(MemoryStore(workbook_state))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("source:monitor_workbook", payload["checks"])

    def test_environment_specific_cors_cookie_and_request_log(self) -> None:
        development = main.create_app(runtime_settings("development"))
        production = main.create_app(runtime_settings("production"))
        self.assertTrue(any(middleware.cls is CORSMiddleware for middleware in development.user_middleware))
        self.assertFalse(any(middleware.cls is CORSMiddleware for middleware in production.user_middleware))

        request = Request({"type": "http", "method": "GET", "path": "/", "headers": [], "query_string": b""})
        with patch.object(cost_api, "settings", runtime_settings("production")):
            cookie_response = Response()
            cost_api.draft_id(request, cookie_response)
        self.assertIn("Secure", cookie_response.headers["set-cookie"])
        self.assertIn("HttpOnly", cookie_response.headers["set-cookie"])
        self.assertIn("SameSite=lax", cookie_response.headers["set-cookie"])

        with self.assertLogs("cost_monitor.request", level="INFO") as captured:
            response = TestClient(development).get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertIn("endpoint=/api/health", captured.output[-1])
        self.assertIn("config_version=", captured.output[-1])
        self.assertIn("reference_version=", captured.output[-1])
        self.assertIn("data_revision=", captured.output[-1])

        with self.assertLogs("cost_monitor.request", level="INFO") as captured:
            response = TestClient(development).get("/api/not-found")
        self.assertEqual(response.status_code, 404)
        self.assertIn("error=http_404", captured.output[-1])


if __name__ == "__main__":
    unittest.main()
