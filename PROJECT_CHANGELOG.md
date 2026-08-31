# Project Changelog

## 2026-08-31 — Iteration 6: formal module source adapter boundaries

### Изменено

- SRV, fuel registry/CBR и monitor workbook оформлены как typed module-owned
  adapters с canonical source-run results.
- Calculation получает immutable `CostMonitorDataset`, а не JSON-shaped state;
  typed activation сериализует обновлённый dataset обратно через local adapter.
- Добавлен узкий Cost Monitor repository contract для read/mutate/audit/data
  revision; `JsonStore` остаётся единственной implementation.

### Architecture

- Physical Excel worksheet/column names принадлежат adapters, а не calculation;
  source и storage остаются разными слоями Cost Monitor.
- Public URLs, response contracts, formulas, data revision semantics, JSON local
  persistence, normal UX и admin contour не изменялись. SQL tooling/migration,
  snapshots/history и shared platform extraction остаются deferred.

### Проверка

- Backend: 40 тестов пройдены, включая typed adapter normalization/round-trip,
  Excel golden master, configuration lifecycle и API contracts.
- Ruff: PASS.
- Frontend: strict TypeScript и production build пройдены.

### Git

- Baseline revision: `ed1fdce` (Iteration 5).
- Commit: see git history.
- Branch: `feature/module-architecture`.

## 2026-08-30 — Iteration 5: read-only configuration admin foundation

### Изменено

- Добавлена отдельная страница `Администрирование` с active-version summary,
  read-only параметрами, source bindings, scenarios и immutable version history.
- Добавлены сравнение immutable versions и отображение structured trace текущего
  in-memory расчёта по плечам, стадиям, компонентам и фактическим значениям.
- Frontend types/API client покрывают active config, versions, comparison,
  `config_version`, `configuration_state` и trace payloads.

### Architecture

- Admin configuration queries загружаются только при входе на страницу, поэтому
  их отказ не влияет на normal Cost Monitor startup, calculation или autosave.
- Контур явно помечен «Только чтение» и не содержит callers для draft/edit/
  activate/rollback. Backend lifecycle, persistence и formulas не изменялись.

### Проверка

- Browser smoke: admin load, active v1/VALID, parameters/history, single-version
  empty state, trace и возврат в calculation/autosave — PASS; console errors: 0.
- Backend: 38 тестов пройдены, включая Excel golden master и API contracts.
- Ruff: PASS.
- Frontend: strict TypeScript и production build пройдены.

### Git

- Baseline revision: `8105e60` (Iteration 4).
- Commit: see git history.
- Branch: `feature/module-architecture`.

## 2026-08-30 — Iteration 4: configuration versions and calculation trace

### Изменено

- Добавлен JSON-backed configuration service с active v1 migration, isolated
  drafts, validation, compare, preview, activation и rollback.
- Active calculation и exports используют versioned configuration и несут
  `config_version`, data revision и structured business trace.
- Введены explicit API DTO/routes и tests для lifecycle, migration, OpenAPI и
  trace/export snapshot.

### Architecture

- Immutable configuration content и active pointer разделены; rollback
  реактивирует существующую validated version без переписывания её правил.
- Обычный Cost Monitor UX не менялся. Admin UI, SQL persistence, auth/RBAC и
  expression evaluator остаются deferred.

### Проверка

- Backend: 38 тестов пройдены, включая Excel golden master, lifecycle и API
  contracts.
- Ruff: PASS.
- Frontend: strict TypeScript и production build пройдены.

### Git

- Baseline revision: `e7db115` (Iteration 3).
- Commit: see git history.
- Branch: `feature/module-architecture`.

## 2026-08-30 — Iteration 3: typed Cost Monitor configuration model

### Изменено

- Добавлена module-owned `configuration/` со строгой Pydantic schema,
  проверяемым baseline, зарегистрированными variables и whitelist primitives.
- Calculation engine получает validated configuration; прежние значения fuel,
  АНО, catering, VAT и НО вынесены без изменения формул или результата.
- Default scenarios, aircraft multipliers и безопасные source identities/masks
  теперь создаются из единого baseline.

### Architecture

- Configuration Definition отделена от будущего Runtime Configuration
  lifecycle. Запрещены unknown fields, arbitrary paths и arbitrary code;
  evaluator, versions, activation, rollback, trace и admin contour не создавались.
- Physical Excel mappings, legacy first-match/rounding и source data остаются в
  adapters/code и зафиксированы как `DEFERRED` либо legacy parity.

### Проверка

- Backend: 33 теста пройдены, включая typed configuration validation, API
  contract и Excel-owned пяти-плечевой golden master.
- Ruff: PASS.
- Frontend: strict TypeScript и production build пройдены.

### Git

- Baseline revision: `6ab0e87` (Iteration 2, подтверждён на local и origin).
- Commit: see git history.
- Branch: `feature/module-architecture`.

## 2026-08-30 — Iteration 2: Cost Monitor configuration inventory

### Изменено

- Добавлен `docs/COST_MONITOR_CONFIGURATION_INVENTORY.md` с полной
  классификацией fuel, НО, АНО, catering, VAT, techstop, M1/M2/M3, lookups,
  rounding, source bindings и fallback rules.

### Architecture

- Отделены module code invariants, будущие safe runtime parameters, business
  data и Excel/Power Query legacy parity. Configuration engine, versions,
  trace и admin contour сознательно не создавались.

### Проверка

- Backend: 29 тестов и Excel golden master пройдены.
- Ruff: PASS.
- Frontend: strict TypeScript и production build пройдены.

### Git

- Commit: see git history.
- Branch: `feature/module-architecture`.

## 2026-08-30 — Iteration 1: module code foundation

### Изменено

- Введены immutable canonical records для тарифов, цен топлива и маршрутов,
  explicit `CalculationResponse` OpenAPI contract и structured diagnostics со
  статусом `complete`/`degraded`; legacy warnings и расчётные числа сохранены.
- `refresh-all` теперь stage/validate/activate набор источников атомарно;
  пустые workbook sections заменяют прежние значения, upload ограничен 25 МБ и
  проверяется как XLSX до публикации, preview использует active file.
- CBR adapter переведён на `httpx`; добавлен Ruff. Frontend рендерит backend
  details без повторных formulas и отменяет/игнорирует stale calculation responses.

### Architecture

- Calculation engine остаётся единственным источником бизнес-формул; JSON
  остаётся local persistence adapter. `pydantic-settings` отложен: текущие
  два path settings не оправдывают новую dependency.

### Проверка

- Backend: 29 тестов пройдены, включая Excel golden master, diagnostics,
  OpenAPI contract, atomic activation, sticky-state и upload safeguards.
- Ruff: PASS — `ruff check backend`.
- Frontend: strict TypeScript и production build пройдены.

### Git

- Commit: see git history.
- Branch: `feature/module-architecture`.

## 2026-08-30 — Iteration 0: baseline and branch initialization

### Изменено

- Каноническая архитектурная спецификация добавлена в
  `docs/AK_CalculateCostPriceFlight_Архитектурное_ТЗ_и_спецификация.md` без
  изменения её содержимого.
- `PROJECT_INDEX.md` теперь указывает на неё как на единственный основной
  architecture reference; `ARCHITECTURE_AUDIT.md` сохранён как исторический
  foundation-аудит.
- Архитектурная инициатива переведена с legacy baseline-ветки
  `codex/architecture-foundation` на `feature/module-architecture`.

### Architecture

- Production code, API, формулы, UX, источники данных и Excel golden fixture
  не изменялись.
- `codex/architecture-foundation` сохранена неизменной baseline-веткой.

### Проверка

- Backend: 26 тестов пройдены, включая Excel-owned пяти-плечевой golden master
  и API contract tests.
- Frontend: strict TypeScript и production build пройдены.
- Ruff: NOT RUN — инструмент пока не настроен в репозитории.

### Git

- Commit: see git history.
- Branch: `feature/module-architecture`.

## 2026-08-30 — Удалены неиспользуемые данные источника и UI-блок снимка

### Изменено

- Удален источник, его parser, экранная конфигурация и устаревшие ссылки в
  документации. Миграция локального хранилища также удаляет неподдерживаемую
  конфигурацию источника.
- С главной страницы расчета удален блок «Снимок данных» и его неиспользуемые
  CSS-стили; `data_snapshot` сохранен в API-результате и экспортах.

### Не изменено

- Расчетные формулы, импортируемые тарифы, порядок first-match, API расчета и
  результаты Excel golden master.

### Проверка

- Backend: 26 тестов пройдено, включая пяти-плечевой Excel golden master.
- Frontend: strict TypeScript и production build пройдены.

## 2026-08-30 — Поведенчески нейтральное разделение внутренних модулей

### Изменено

- Файловый ввод, семейства Excel-парсеров и применение импорта разделены на
  самостоятельные модули; `sources.py` оставлен координатором обновления.
- Cost Monitor JSON store перенесён из общего `core` внутрь feature-модуля.
- Страницы калькулятора, источников, тарифов и настроек вынесены из
  `CostMonitorApp.tsx`; общие форматтеры собраны отдельно.
- Существующие Python docstring’и и значимые алгоритмические комментарии
  переведены на русский и немного уточнены.

### Добавлено

- Characterization fixtures для SRV, реестра топлива и основной книги
  монитора, фиксирующие текущий порядок, отбор и преобразование данных.

### Не изменено

- API URL/JSON, расчётные формулы, округление, порядок тарифов, тексты и
  JSX/CSS интерфейса.
- Дублирующие формулы клиентской детализации оставлены до отдельной фиксации
  контракта округления: преждевременная замена могла изменить показ на 1 ₽.

### Проверка

- Backend: 25 тестов пройдено, включая Excel golden master и API contract.
- Frontend: strict TypeScript и production build пройдены.

## 2026-08-30 — Architecture foundation and feature boundaries

### Changed

- Reduced `backend/app/main.py` to the FastAPI composition root.
- Grouped Cost Monitor API, schemas, calculation, exports and source imports
  under `backend/app/modules/cost_monitor/` without changing URLs or JSON.
- Removed the calculation -> source-import dependency by extracting the stable
  tariff catalog helpers.
- Grouped the current frontend application, API client and types under
  `frontend/src/features/cost-monitor/`; kept `frontend/src/App.tsx` as the
  stable root entry.

### Added

- Excel-owned five-leg golden fixture captured from the approved workbook.
- Golden parity tests for raw component values and M1/M2/M3 totals.
- API operation/export shape contract tests.
- Characterization tests for partial refresh and the current CBR fallback.

### Removed

- The generic-looking `backend/app/services/` package; its contents belonged to
  the Cost Monitor feature.

### Architecture

- Established the first backend and frontend feature boundaries for adding
  future independent monitors.
- Preserved the modular-monolith deployment and existing persistence adapter.

### Validation

- Backend tests: 21 passed.
- Excel parity: approved five-leg scenario passed against cached workbook values.
- Frontend typecheck/build: passed.

### Git

- Commit: pending / see git history.
- Branch: `codex/architecture-foundation`.

## 2026-08-30 — Architecture audit baseline

### Changed

- Production source code, API, calculation formulas, UI and runtime behavior:
  unchanged.

### Added

- `ARCHITECTURE_AUDIT.md` with current architecture, prioritized findings,
  reliability/security review, target structure and staged migration.
- `PROJECT_INDEX.md` as the persistent navigation map for future work.
- `PROJECT_CHANGELOG.md` as the internal technical change journal.

### Removed

- Nothing.

### Architecture

- Recorded the current FastAPI + React modular-monolith baseline.
- Identified Excel golden-master parity as the gate before structural refactoring.
- Proposed `codex/architecture-foundation` as the future architecture branch;
  the branch was intentionally not created during the audit.

### Validation

- Backend tests: 15 passed (`python -m unittest discover`).
- Frontend typecheck/build: passed (`tsc -b && vite build`).
- Python dependency check: passed (`pip check`).
- Runtime versions observed: Python 3.12.2, pnpm 11.19.0, Node 25.2.1.

### Git

- Commit: pending / see git history.
- Branch: `main`.
- Starting working tree: clean.
