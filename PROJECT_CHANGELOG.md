# Project Changelog

## 2026-08-30 — Удален неиспользуемый источник надбавок и скидок

### Изменено

- Удален источник, его parser, экранная конфигурация и устаревшие ссылки в
  документации. Миграция локального хранилища также удаляет неподдерживаемую
  конфигурацию источника.

### Не изменено

- Расчетные формулы, импортируемые тарифы, порядок first-match, API расчета и
  результаты Excel golden master.

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
