# Project Index

Карта отражает текущее состояние репозитория на 2026-08-31. Каноническая
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
- `frontend/src/App.tsx` — route entry: `/` открывает пользовательский Cost
  Monitor, `/admin` — отдельный administrative contour.
- Dev: `cd frontend; pnpm dev`.

## Backend

### Cost Monitor feature

- `backend/app/modules/cost_monitor/api.py` — feature router, JSON store
  composition, health/dashboard, calculation/options, user drafts, independent
  versioned Configuration and Reference Data lifecycles, exports,
  sources/upload/refresh/preview, tariffs, routes и audit.
- `backend/app/modules/cost_monitor/schemas.py` — request DTO и явный
  `CalculationResponse` contract с diagnostics/status для `/api/calculations`.
- `backend/app/modules/cost_monitor/records.py` — immutable canonical records,
  live `CostMonitorDataset` и separate `CostMonitorReferenceSnapshot`:
  calculation получает активные live/config/reference snapshots, сохраняя
  physical first-match order.
- `backend/app/modules/cost_monitor/catalog.py` — нормализация ключей и stable
  imported-before-manual tariff view shared by calculation and source import.
- `backend/app/modules/cost_monitor/source_adapters.py` — отдельные production
  adapters для SRV/Fuel Registry и compatibility adapter для Legacy Monitor
  Workbook; физические Excel bindings не проникают в calculation.
- `backend/app/modules/cost_monitor/reference_data/` — typed schema, checked-in
  `defaults/` (500 ВВЛ routes и 45 Airport Other Costs), validation,
  JsonStore repository и lifecycle service. Git seeds не переписываются из
  runtime edits; active version/drafts/audit остаются module-local.
- `backend/app/modules/cost_monitor/baselines.py` и `baselines/manual_tariffs.json`
  — one-time seed только для 10 manual tariffs из утверждённой legacy-книги.
- `backend/app/modules/cost_monitor/store.py` и `repository.py` — local JSON
  implementation и узкий persistence contract для read/mutate/audit/data
  revision; versioned Reference Data хранится независимо и его activation не
  меняет `data_revision`.
- `backend/app/modules/cost_monitor/configuration/` — schema `2.0`, module
  definition, effective context, typed operation executor и capability-oriented
  JSON lifecycle: immutable versions, drafts, validate/preview/compare/activate/
  rollback, configuration-owned aircraft/scenario values and provenance.

### Calculation and export

- `backend/app/modules/cost_monitor/calculation.py` — orchestration Cost
  Monitor; ANO/Catering/VAT исполняются через typed config operations, Ground
  сохраняет legacy matrix, diagnostics и business-readable provenance trace.
- `backend/app/modules/cost_monitor/exports.py` — единый export snapshot и JSON/XLSX writers;
  не должен выполнять тарифные lookup или изменять результат.

### Data sources

- `backend/app/modules/cost_monitor/sources.py` — production-only typed
  source-run stage/activate orchestration для SRV и Fuel Registry; `refresh-all`
  атомарно публикует canonical dataset только при успехе обоих источников.
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

- `frontend/src/features/cost-monitor/CostMonitorApp.tsx` — пользовательский
  application shell без administrative workflow; `AdminApp.tsx` — отдельный
  lazy-loaded lifecycle UI для `/admin`.
- `frontend/src/features/cost-monitor/pages/` — user pages, editable
  Configuration `AdminPage` и draft-only `ReferenceDataAdmin`: Routes/Airport
  Other Costs search, row editing, preview, compare, activate/rollback и trace.
- `frontend/src/features/cost-monitor/formatting.ts` — общие форматтеры чисел,
  сумм и времени для feature-страниц.
- `frontend/src/styles.css` — все стили приложения.

### API and types

- `frontend/src/features/cost-monitor/api.ts` — Cost Monitor `/api` client,
  upload/export и typed Configuration/Reference Data lifecycle calls.
- `frontend/src/features/cost-monitor/types.ts` — вручную поддерживаемые
  TypeScript request/response types, включая configuration lifecycle и trace.
- `frontend/src/features/cost-monitor/index.ts` — feature entry.
- `frontend/vite.config.ts` — dev proxy `/api -> localhost:8000`.

## Tests and validation

- `backend/tests/test_calculator.py` — synthetic calculation cases.
- `backend/tests/test_sources.py` — parser/adapter normalization, preview/upload
  safeguards, atomic source activation, sticky-state regression, manual conflict
  и CBR fallback.
- `backend/tests/test_exports.py` — shared JSON/XLSX snapshot packaging.
- `backend/tests/test_store.py` — JSON persistence, repository boundary,
  baseline seed и one-time legacy workbook migration.
- `backend/tests/test_configuration.py` — typed baseline, safety restrictions,
  зарегистрированные capabilities и инъекция validated configuration в расчёт.
- `backend/tests/test_configuration_service.py` — lifecycle v1/draft/validate/
  compare/preview/activate/rollback и изоляция configuration от user drafts.
- `backend/tests/test_reference_data.py` — typed reference payload validation,
  immutable active snapshot, draft/compare/preview/activate/rollback, audit и
  независимость `config_version`/`reference_version`/`data_revision`.
- `backend/tests/test_excel_parity.py` и
  `backend/tests/fixtures/excel_cost_monitor_baseline.json` — Excel-owned
  пяти-плечевой golden master и calculation/export shape.
- `backend/tests/test_api_contract.py` — стабильный набор API operations,
  explicit OpenAPI response contract и atomic refresh-all characterization.
- `ruff.toml` — минимальный backend lint gate.
- Backend: `$env:PYTHONPATH=(Resolve-Path .\backend).Path; .\.venv\Scripts\python -m unittest discover -s .\backend\tests -v`.
- Frontend: `cd frontend; pnpm build` (strict TypeScript + Vite production build).
- Текущий полный набор: 54 backend tests; `\.venv\Scripts\ruff check backend`.

## Documentation and analysis

- `README.md` — local setup, validation commands и runtime overview.
- `docs/AK_CalculateCostPriceFlight_Архитектурное_ТЗ_и_спецификация.md` —
  единственный канонический архитектурный документ: целевая модель,
  инварианты, roadmap и правила выполнения итераций.
- `docs/AK_CalculateCostPriceFlight_PRE_RELEASE_ARCHITECTURE.md` —
  утверждённая предрелизная модель: граница DEV/PROD, независимость runtime
  от Legacy Monitor Workbook и план подготовки ветки `release/v1.0.0`.
- `docs/COST_MONITOR_CONFIGURATION_INVENTORY.md` — ownership matrix, schema
  `2.0`, operation/override boundaries и current administrative lifecycle.
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
- `/admin` lazy-loads its independent admin application; отсутствие admin API
  не влияет на normal Cost Monitor startup. Authentication/RBAC пока нет.
- Клиентская детализация рендерит backend `details`; формулы АНО/питания/НДС
  на frontend не дублируются.
- `JsonStore` безопасен только для одного процесса; shared deployment требует
  транзакционного persistence.
- Legacy Monitor Workbook принадлежит compatibility tooling и не участвует в
  startup, source UI, source refresh или calculation lifecycle release runtime.
- Release v1 — ВВЛ-only: `international_airports` и МВЛ ground branches
  отсутствуют в production dataset/calculation; parser `Признак МВЛ` остаётся
  только DEV compatibility tooling.
- Configuration v1 — единственный production owner aircraft multipliers и
  M1/M2/M3 scenario rates. Active Reference Data — единственный production
  owner Routes и Airport Other Costs; его lifecycle API и `/admin` draft-only
  UI независимы от Configuration и live `data_revision`. Bulk CSV/XLSX import
  остаётся deferred.
- Physical Excel names принадлежат module-local adapters; calculation получает
  только `CostMonitorDataset` и не зависит от JSON, filesystem или будущего SQL.
- Активная ветка архитектурной инициативы — `feature/module-architecture`.
  `codex/architecture-foundation` сохранена как baseline foundation-версии.
