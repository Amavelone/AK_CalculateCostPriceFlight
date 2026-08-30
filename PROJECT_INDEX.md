# Project Index

Карта отражает текущее состояние репозитория на 2026-08-30. Каноническая
архитектурная модель, инварианты и порядок развития описаны в
`docs/AK_CalculateCostPriceFlight_Архитектурное_ТЗ_и_спецификация.md`.
`ARCHITECTURE_AUDIT.md` сохраняет исторический аудит foundation-версии.

## Entry Points

Backend:
- `backend/app/main.py` — FastAPI composition root: middleware, Cost Monitor
  router и раздача `frontend/dist`.
- Dev: `python -m uvicorn app.main:app --app-dir backend --reload --port 8000`.

Frontend:
- `frontend/src/main.tsx` — React bootstrap.
- `frontend/src/App.tsx` — стабильный root entry, реэкспортирующий Cost Monitor
  feature.
- Dev: `cd frontend; pnpm dev`.

## Backend

### Cost Monitor feature

- `backend/app/modules/cost_monitor/api.py` — feature router, JSON store
  composition, health/dashboard, calculation/options, user drafts, versioned
  configuration lifecycle, exports, sources/upload/refresh/preview, tariffs,
  routes и audit.
- `backend/app/modules/cost_monitor/schemas.py` — request DTO и явный
  `CalculationResponse` contract с diagnostics/status для `/api/calculations`.
- `backend/app/modules/cost_monitor/records.py` — immutable canonical records
  тарифов, цен топлива и маршрутов на границе JSON state → calculation engine.
- `backend/app/modules/cost_monitor/catalog.py` — нормализация ключей и stable
  imported-before-manual tariff view shared by calculation and source import.
- `backend/app/modules/cost_monitor/store.py` — default state, миграция,
  атомарный JSON read/mutate, audit log и data revision этого feature.
- `backend/app/modules/cost_monitor/configuration/` — typed definition и
  module-owned JSON-backed lifecycle service: immutable active versions,
  isolated drafts, validation, compare, activation и rollback. SQL persistence
  остаётся deferred; Iteration 5 добавляет отдельный read-only frontend contour.

### Calculation and export

- `backend/app/modules/cost_monitor/calculation.py` — источник истины для всех формул Cost
  Monitor; возвращает legs, totals, legacy warnings, structured diagnostics,
  status, `data_snapshot`, `config_version` и structured business trace.
- `backend/app/modules/cost_monitor/exports.py` — единый export snapshot и JSON/XLSX writers;
  не должен выполнять тарифные lookup или изменять результат.

### Data sources

- `backend/app/modules/cost_monitor/sources.py` — stage/activate orchestration;
  `refresh-all` публикует набор только при успехе всех обязательных sources.
- `backend/app/modules/cost_monitor/source_files.py` — ограниченный по размеру,
  проверяемый XLSX upload и preview активированного файла.
- `backend/app/modules/cost_monitor/parsers/` — общие преобразования и
  изолированные SRV, fuel/CBR и monitor-workbook парсеры.
- `backend/data/store.json` — runtime data, drafts и audit; игнорируется Git.

### Persistence and configuration

- `backend/app/core/config.py` — project/data/source paths из environment.
- Environment: `MONITOR_DATA_DIRECTORY`, `MONITOR_SOURCE_DIRECTORY`.

## Frontend

### App and pages

- `frontend/src/features/cost-monitor/CostMonitorApp.tsx` — application shell,
  autosave, data refresh, API orchestration, stale-request protection и
  отдельная lazy-loaded navigation group для администрирования.
- `frontend/src/features/cost-monitor/pages/` — отдельные страницы калькулятора,
  источников, тарифов, настроек и read-only `AdminPage` для active
  configuration, immutable versions, compare и текущего calculation trace.
- `frontend/src/features/cost-monitor/formatting.ts` — общие форматтеры чисел,
  сумм и времени для feature-страниц.
- `frontend/src/styles.css` — все стили приложения.

### API and types

- `frontend/src/features/cost-monitor/api.ts` — Cost Monitor `/api` client,
  upload, calculation export download и read-only configuration queries.
- `frontend/src/features/cost-monitor/types.ts` — вручную поддерживаемые
  TypeScript request/response types, включая configuration lifecycle и trace.
- `frontend/src/features/cost-monitor/index.ts` — feature entry.
- `frontend/vite.config.ts` — dev proxy `/api -> localhost:8000`.

## Tests and validation

- `backend/tests/test_calculator.py` — synthetic calculation cases.
- `backend/tests/test_sources.py` — parser fixtures, preview/upload safeguards,
  atomic source activation, sticky-state regression, manual conflict и CBR fallback.
- `backend/tests/test_exports.py` — shared JSON/XLSX snapshot packaging.
- `backend/tests/test_store.py` — JSON persistence и legacy revision migration.
- `backend/tests/test_configuration.py` — typed baseline, safety restrictions,
  зарегистрированные capabilities и инъекция validated configuration в расчёт.
- `backend/tests/test_configuration_service.py` — lifecycle v1/draft/validate/
  compare/preview/activate/rollback и изоляция configuration от user drafts.
- `backend/tests/test_excel_parity.py` и
  `backend/tests/fixtures/excel_cost_monitor_baseline.json` — Excel-owned
  пяти-плечевой golden master и calculation/export shape.
- `backend/tests/test_api_contract.py` — стабильный набор API operations,
  explicit OpenAPI response contract и atomic refresh-all characterization.
- `ruff.toml` — минимальный backend lint gate.
- Backend: `$env:PYTHONPATH=(Resolve-Path .\backend).Path; .\.venv\Scripts\python -m unittest discover -s .\backend\tests -v`.
- Frontend: `cd frontend; pnpm build` (strict TypeScript + Vite production build).
- Текущий полный набор: 38 backend tests; `\.venv\Scripts\ruff check backend`.

## Documentation and analysis

- `README.md` — local setup, validation commands и runtime overview.
- `docs/AK_CalculateCostPriceFlight_Архитектурное_ТЗ_и_спецификация.md` —
  единственный канонический архитектурный документ: целевая модель,
  инварианты, roadmap и правила выполнения итераций.
- `docs/COST_MONITOR_CONFIGURATION_INVENTORY.md` — classification правил из
  Iteration 2, typed baseline Iteration 3, lifecycle boundaries Iteration 4 и
  read-only admin boundary Iteration 5.
- `ARCHITECTURE_AUDIT.md` — исторический аудит foundation-версии и исходные
  findings; не является текущим canonical architecture reference.
- `PROJECT_CHANGELOG.md` — значимые технические изменения от этого аудита.
- `docs/cost-monitor-business-logic.md` — утверждённый calculation baseline.
- `docs/cost-monitor-analysis.md` — reverse engineering исходного Excel.
- `docs/cost-monitor-dependency-map.md` — Excel и web data flow.
- `docs/cost-monitor-architecture-plan.md` — первоначальное решение MVP.
- `analysis/xlsx-inventory.json` и `tools/*.py` — исследовательские артефакты и
  скрипты инвентаризации; не входят в production runtime.

## Important invariants

- Preserve behavior first; improve architecture second.
- Excel calculation parity, physical first-match order, formulas, rounding и
  итоговые M1/M2/M3 нельзя менять неявно.
- Frontend не должен становиться источником calculation formulas; backend result
  и details — источник истины.
- JSON и XLSX exports должны представлять один completed calculation snapshot.
- Manual tariffs дополняют отсутствующие ключи, не override imported tariff;
  imported rows идут первыми.
- Failed source parse не должен уничтожать предыдущие активные parsed data.
- `PROJECT_INDEX.md` обновляется после изменения структуры/ответственностей.
- `PROJECT_CHANGELOG.md` обновляется после значимых изменений проекта.
- Перед существенным refactoring нужен Excel-owned golden-master parity suite.

## Known architecture seams

- Backend Cost Monitor сгруппирован по feature; файловый ввод, семейства
  парсеров, оркестрация источников и JSON adapter имеют отдельные границы.
- Frontend страницы разделены; следующий безопасный seam — hooks только после
  фиксации autosave/API sequence отдельными тестами.
- Read-only admin APIs загружаются только при входе в отдельный admin contour;
  их отказ не входит в normal Cost Monitor startup path.
- Клиентская детализация рендерит backend `details`; формулы АНО/питания/НДС
  на frontend не дублируются.
- `JsonStore` безопасен только для одного процесса; shared deployment требует
  транзакционного persistence.
- Активная ветка архитектурной инициативы — `feature/module-architecture`.
  `codex/architecture-foundation` сохранена как baseline foundation-версии.
