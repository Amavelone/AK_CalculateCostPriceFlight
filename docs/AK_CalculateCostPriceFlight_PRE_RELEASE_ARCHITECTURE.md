# AK_CalculateCostPriceFlight — Предрелизная архитектура и модель release-ветки

## Статус документа

Этот документ фиксирует целевую модель подготовки `AK_CalculateCostPriceFlight` к первому production release после завершения архитектурных итераций `feature/module-architecture`.

Он не заменяет основную архитектурную спецификацию проекта. Здесь фиксируется именно предрелизная модель: граница DEV/PROD, судьба исходного Excel Monitor, внутренние справочники модуля, live sources, release hardening и Git workflow.

---

# 1. Главная цель

К моменту первого полноценного release роль Excel меняется:

```text
Раньше:
Excel Monitor -> runtime source -> Web Monitor

Цель:
Excel Monitor -> DEV compatibility / parity / migration tool

Production Web Monitor -> самостоятельный runtime
```

Ключевой принцип:

> **Excel остаётся эталоном совместимости и инструментом разработки, но перестаёт быть обязательной runtime-зависимостью production-сервиса.**

Production release должен запускаться и выполнять расчёты без наличия исходного файла `Расчет себестоимости рейсов*.xlsx`.

---

# 2. DEV и RELEASE

## DEV

Development-ветки могут сохранять:

- `MonitorWorkbookAdapter`;
- parser исходного Monitor Workbook;
- Excel golden/parity tests;
- сравнение новой версии Excel с web baseline;
- migration tooling;
- экспериментальные ветки;
- анализ изменений методологии Excel.

```text
Legacy Excel Monitor
        ↓
Compatibility Adapter
        ↓
Canonical Candidate
        ↓
Diff / Parity
        ↓
Config / Reference / Code changes
```

## RELEASE / PROD

Release-ветка должна быть независима от Monitor Workbook как runtime source.

**Выполнено в Iteration 1:** release runtime регистрирует только SRV и Fuel
Registry. Workbook parser/adapter остаются отдельным compatibility tooling для
DEV parity и migration, но отсутствуют в startup, persisted production source
configuration, source UI и `refresh-all`.

```text
Release v1
    ├── Calculation Configuration
    ├── Module-owned Reference Data
    ├── Internal Manual Data
    ├── SRV live source
    └── Fuel Registry live source
```

Исходный Excel Monitor не участвует в startup, `refresh-all`, production calculation, readiness и production source configuration.

---

# 3. Новая роль Excel

Excel становится:

1. **Compatibility Oracle** — эталон regression/parity.
2. **Migration Source** — источник однократного переноса legacy-справочников.
3. **Development Tool** — инструмент анализа будущих изменений Excel.
4. **Reference Implementation** — происхождение первоначальной методологии.

Excel не является production master system.

---

# 4. Миграция содержимого Monitor Workbook

## 4.1. `ИШР`

Поля:

- departure;
- arrival;
- distance;
- flight_time.

Production owner:

> **Module-owned Versioned Reference Data → Routes**

---

## 4.2. `Признак МВЛ`

Для release v1 **полностью исключается**.

Не переносится ни в config, ни в reference data, ни в другой source.

Release v1 фиксируется как требуемый ВВЛ-контур.

Это означает постепенное исключение из production runtime:

- `international_airports`;
- parser листа `Признак МВЛ`;
- определения `line_type` через Excel;
- обязательства поддерживать МВЛ в v1.

Это сознательное изменение функционального scope v1.

---

## 4.3. Aircraft multipliers

Production owner:

> **Calculation Configuration**

Значения должны быть versioned, editable через `/admin`, поддерживать validation/trace и не иметь второго silent source of truth.

---

## 4.4. Scenario rates M1/M2/M3

Production owner:

> **Calculation Configuration**

Production больше не получает их из Monitor Workbook.

---

## 4.5. `Прочее`

Аэропортовые дополнительные значения становятся внутренним справочником:

> **Module-owned Reference Data → Airport Other Costs**

Через `/admin` записи можно добавлять, изменять, удалять, валидировать, активировать и откатывать.

---

## 4.6. `ЦРТ+`

Один раз мигрируется:

```text
Excel ЦРТ+
    ↓ one-time migration
Internal Manual Tariff Catalog
```

После этого production больше не читает `ЦРТ+`.

---

# 5. Production Live Sources

В production остаются только реальные внешние sources:

## SRV

Актуальные тарифы.

## Fuel Registry

Актуальные цены топлива.

```text
SRV -> SrvTariffsAdapter
Fuel Registry -> FuelRegistryAdapter
        ↓
Canonical Live Dataset
```

Monitor Workbook относится только к compatibility/migration tooling.

---

# 6. Module-owned Versioned Reference Data

В Cost Monitor вводится отдельный слой:

> **Reference Data**

Он не смешивается с Calculation Configuration.

### Configuration отвечает:

> Как считать?

Примеры: коэффициенты, operations, conditions, rounding, M1/M2/M3, aircraft multipliers.

### Reference Data отвечает:

> На каких внутренних справочных данных считать?

Примеры: маршруты, расстояние, время полёта, прочие аэропортовые расходы.

---

# 7. Рекомендуемая структура модуля

```text
backend/app/modules/cost_monitor/
│
├── configuration/
│   └── ...
│
├── reference_data/
│   ├── schema.py
│   ├── definition.py
│   ├── defaults/
│   │   ├── routes.json
│   │   └── airport_other_costs.json
│   ├── validation.py
│   ├── repository.py
│   └── service.py
│
├── source_adapters.py
├── records.py
├── calculation.py
└── ...
```

Точные имена могут отличаться.

Ключевая граница:

```text
Configuration != Reference Data != Live Sources
```

---

# 8. Baseline Reference Data

В repository хранится утверждённый baseline внутренних справочников.

Например:

```text
reference_data/defaults/routes.json
```

Пример:

```json
{
  "schema_version": 1,
  "baseline_source": "approved legacy monitor",
  "baseline_date": "2026-08-31",
  "records": [
    {
      "departure": "DME",
      "arrival": "KJA",
      "distance": 3352.0,
      "flight_time": 4.633333333333
    }
  ]
}
```

Baseline-файлы являются seed и хранятся в Git.

Admin editing не должен переписывать эти Git-файлы.

---

# 9. Runtime Reference Data

После первого запуска baseline создаёт:

```text
ACTIVE Reference v1
```

Дальше:

```text
Create Draft
↓
Edit
↓
Validate
↓
Preview / Compare
↓
Activate
↓
Rollback
```

Active version immutable.

Текущая реализация может использовать `JsonStore`; позже storage adapter может перейти на SQL Server.

---

# 10. Независимые версии

Не смешивать:

```text
Calculation Config Version
Reference Data Version
Live Data Revision
```

Пример:

```text
Config:       v12
Reference:    v7
Live dataset: revision 31
```

Calculation result постепенно должен уметь возвращать все три идентификатора.

---

# 11. Effective Calculation Context

```text
Active Calculation Configuration
            +
Active Reference Data
            +
Active Live Source Dataset
            ↓
Effective Calculation Context
            ↓
Calculation Engine
```

Provenance каждого слоя сохраняется.

---

# 12. Admin UI

Админка остаётся на:

```text
/admin
```

Для локальной production-like сборки:

```text
http://127.0.0.1:8000/admin
```

Структура:

```text
/admin
├── Расчётная схема
├── Справочники
│   ├── Routes
│   └── Airport Other Costs
├── Источники
│   ├── SRV
│   └── Fuel Registry
└── Trace / Audit
```

---

# 13. Reference Data CRUD

## Routes

Поля:

- departure;
- arrival;
- distance;
- flight_time.

Ключ:

```text
departure + arrival
```

Validation:

- departure/arrival заданы;
- unique route key;
- distance >= 0;
- flight_time >= 0.

## Airport Other Costs

Поля:

- airport;
- amount.

Validation:

- airport unique;
- amount >= 0.

Изменения производятся только через draft lifecycle.

---

# 14. Bulk Import

Допустим controlled import:

```text
CSV / XLSX
↓
Parse
↓
Reference Draft Candidate
↓
Validation
↓
Diff
↓
Activate
```

Файл — одноразовый вход. После activation он не является runtime dependency.

---

# 15. Manual Tariffs

Manual tariffs могут остаться отдельным Cost Monitor catalog:

```text
Imported SRV tariffs + Manual tariffs
```

Не обязательно затаскивать их в generic Reference Data.

---

# 16. Целевой состав данных calculation

## Live

- imported tariffs;
- manual tariffs;
- fuel prices.

## Reference

- routes;
- other costs.

## Configuration

- aircraft multipliers;
- scenario rates;
- formulas;
- operations;
- parameters.

## Removed from v1

- international airports;
- МВЛ lookup.

---

# 17. Новый parity contract

Перед release контракт уточняется:

> **Default production baseline повторяет утверждённый Excel Monitor в пределах функционального scope release v1.**

```text
ВВЛ              required
ЦРТ              required
АК               required, если входит в v1
techstop         required
catering         required
M1/M2/M3         required
МВЛ              OUT OF SCOPE v1
```

Golden expected values нельзя регенерировать из нового Python calculator.

---

# 18. Git model

Текущая development ветка:

```text
feature/module-architecture
```

От неё создаётся:

```text
release/v1.0.0
```

Release branch получает:

- decoupling от Monitor Workbook;
- migrated Reference Data;
- исключение МВЛ из v1;
- release hardening;
- production configuration;
- final validation.

DEV продолжает сохранять Excel compatibility.

---

# 19. Release Identity

Production calculation должен идентифицироваться через:

```text
Application release
Calculation config version
Reference data version
Live data revision
```

Например:

```text
App:       1.0.0
Config:    12
Reference: 7
Data:      31
```

---

# 20. Release Hardening

Перед v1.0.0 проверить:

- явную production environment configuration;
- отсутствие developer Downloads fallback;
- repository visibility/secrets;
- admin security boundary;
- JsonStore single-process/single-worker constraint;
- backup/restore;
- `/api/health`;
- `/api/ready`;
- production logging;
- CI;
- protected `main`;
- application version `1.0.0`;
- reproducible dependencies;
- production build/start procedure.

---

# 21. Production Runtime

Не использовать:

```text
--reload
pnpm dev
```

Production:

```text
pnpm build
↓
frontend/dist
↓
FastAPI serves /
FastAPI serves /admin
↓
single worker while JsonStore
```

---

# 22. Release Validation Matrix

| Scenario | Gate |
|---|---|
| ВВЛ + ЦРТ | required |
| ВВЛ + АК | required if supported |
| techstop | required |
| no techstop | required |
| catering ON/OFF | required |
| missing route | required |
| missing tariff | required |
| config change/rollback | required |
| reference change/rollback | required |
| source refresh failure | required |
| JSON/XLSX export | required |
| `/admin` | required |
| `/api/health` | required |
| `/api/ready` | required |

---

# 23. Final Release Workflow

```text
feature/module-architecture
        ↓
release/v1.0.0
        ↓
release iterations
        ↓
Release Candidate
        ↓
full validation
        ↓
PR to main
        ↓
user approval
        ↓
merge main
        ↓
tag v1.0.0
        ↓
production deployment
```

Codex не должен автоматически merge/tag/deploy без отдельной команды пользователя.

---

# 24. Итоговая архитектура v1

```text
LEGACY EXCEL
     │
     │ DEV ONLY
     ▼
Compatibility / Migration / Parity


                PRODUCTION COST MONITOR
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
   Calculation       Reference       Live
   Configuration       Data         Sources
          │              │              │
      HOW TO          WHAT WE        CURRENT
      CALCULATE        KNOW           DATA
          │              │              │
      formulas         routes           SRV
      operations       other costs      Fuel
      parameters
      M1/M2/M3
      multipliers
          │              │              │
          └──────────────┼──────────────┘
                         ▼
              Effective Calculation Context
                         ▼
                   Calculation
```

> **Release v1 является самостоятельным web-приложением. Excel больше не является runtime dependency, но сохраняется в DEV как эталон совместимости и источник миграции.**

---

# 25. Release Repository Cleanup

Release-ветка должна быть очищена от документов и артефактов, которые использовались только для ведения разработки, Codex-навигации и промежуточного архитектурного процесса.

Цель:

> **В `release/v1.0.0` остаётся только то, что нужно для эксплуатации, сопровождения, понимания production-кода и будущей разработки продукта.**

Не следует переносить в production repository line временную «память процесса разработки».

## 25.1. Кандидаты на удаление из release-ветки

Перед удалением обязательно проверить фактическое назначение каждого файла.

Типичные development-only документы:

```text
PROJECT_INDEX.md
PROJECT_CHANGELOG.md
ARCHITECTURE_AUDIT.md
MODULE_ARCHITECTURE_EXECUTION_PLAN.md
итерационные Codex prompts
временные review/audit reports
analysis/*
output/*
tmp/*
локальные migration dumps
временные parity/exploration artifacts
```

Если какой-либо документ содержит уникальную production-важную информацию:

1. перенести эту информацию в canonical production documentation;
2. затем удалить development-only файл.

Не удалять полезную информацию без миграции.

## 25.2. Что должно остаться

Минимальный production documentation set:

```text
README.md
docs/
  ARCHITECTURE.md           # если реально нужен разработчикам
  DEPLOYMENT.md             # production setup / start / backup / restore
  CONFIGURATION.md          # admin/config/reference data model
  OPERATIONS.md             # health, readiness, logs, recovery
```

Точные имена могут отличаться.

Не создавать документацию ради количества файлов.

## 25.3. `.gitignore`

Release `.gitignore` должен исключать:

```text
.env
.env.*
!.env.example

.venv/
__pycache__/
*.py[cod]
.pytest_cache/
.ruff_cache/

backend/data/
frontend/node_modules/
frontend/dist/

output/
tmp/
logs/
*.log

IDE/editor files
OS temporary files
local source Excel/CSV files
runtime uploads
backup files
local development exports
temporary analysis artifacts
```

Дополнительно добавить шаблоны development-only документов/рабочих файлов, если они могут появляться повторно после release.

Важно:

> `.gitignore` не удаляет уже tracked files.

Development-only tracked documents должны быть явно удалены из release branch после переноса нужной информации в production docs.

---

# 26. Code Maintainability and Comments

Перед release весь production code должен пройти maintainability review.

Цель:

> Другой разработчик должен понимать архитектурные границы, business-sensitive места и причины неочевидных решений без необходимости читать историю Codex-итераций.

## Комментарии нужны там, где объясняется WHY

Хорошие комментарии:

- почему сохраняется Excel first-match semantics;
- почему rounding выполняется именно на этом этапе;
- почему используется single-worker при JsonStore;
- почему конкретное legacy поведение намеренно сохранено;
- где проходит boundary Config / Reference Data / Live Source;
- почему operation configuration ограничена whitelist;
- почему source activation atomic;
- какие invariants критичны для parity.

## Не комментировать очевидное

Не писать комментарии вида:

```python
# увеличиваем i
i += 1
```

или:

```python
# возвращаем результат
return result
```

## Docstrings

Публичные и архитектурно значимые:

- services;
- repositories;
- adapters;
- configuration executor;
- reference-data services;
- calculation orchestration;
- public utility functions

должны иметь короткие полезные docstrings, описывающие ответственность и важные ограничения.

Не превращать код в учебник.

## Cleanup

Удалить:

- stale comments;
- комментарии, описывающие уже несуществующую архитектуру;
- TODO без owner/смысла;
- Codex-specific комментарии;
- временные debug notes;
- закомментированный мёртвый код.

---

# 27. Production README

Перед Release Candidate `README.md` должен быть полностью переписан из dev-oriented README в production/project README.

README должен давать новому разработчику и оператору быстрый вход.

Минимальная структура:

## Project

- что делает Cost Monitor;
- business purpose;
- supported v1 scope;
- явно: МВЛ out of scope v1.

## Architecture

Коротко:

```text
Calculation Configuration
+
Reference Data
+
Live Sources
-> Calculation
```

Excel Monitor:

```text
DEV compatibility only
```

## Requirements

- Python version;
- Node/pnpm version;
- OS/deployment assumptions;
- single-worker restriction при JsonStore.

## Configuration

- environment variables;
- `.env.example`;
- source directories;
- data directory.

## Development

Краткий dev start без внутренней истории итераций.

## Build

Frontend production build.

## Production Start

Точная команда без `--reload`.

## Routes

```text
/
/admin
/api/health
/api/ready
```

## Data

- Calculation Configuration;
- Reference Data;
- SRV;
- Fuel Registry;
- storage location.

## Tests

Фактические commands.

## Backup / Restore

Ссылка или краткая инструкция.

## Known Limitations

Только актуальные ограничения release.

Не оставлять в README:

- старые архитектурные планы;
- roadmap завершённых итераций;
- инструкции для Codex;
- историю рефакторинга;
- устаревшие dev ограничения.

---

# 28. Release Repository Definition

Итоговый release repository должен восприниматься как обычный поддерживаемый software project, а не как архив процесса его создания.

Проверка перед RC:

```text
clone repository
↓
прочитать README
↓
понять architecture
↓
настроить environment
↓
запустить tests
↓
build
↓
start production-like instance
```

без необходимости читать:

```text
Codex prompts
iteration logs
architecture audit history
project indexing files
conversation-derived notes
```

