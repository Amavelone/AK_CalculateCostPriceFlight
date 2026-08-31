# Cost Monitor Configuration Inventory

## Статус и назначение

**Iteration:** Release Iteration 4 — Reference Data Administration.
**Статус:** active configuration schema `2.0` содержит typed parameters,
operation parts, safe conditions/lookups и versioned configuration-owned
aircraft/scenario values.
ANO, Catering и VAT выполняются через Cost Monitor-owned operation executor.
Configuration и Reference Data имеют независимые immutable active versions,
draft/validate/compare/preview/activate/rollback API. Отдельный `/admin`
управляет обоими draft workflows: Reference Data UI редактирует только full
typed draft payload. CSV/XLSX bulk import, Sources и Audit остаются вне scope
этой административной секции.

Документ фиксирует фактические правила foundation-версии и их текущее место
ответственности. Typed baseline воспроизводит прежние Python/Excel значения и
защищён Excel golden master. Изменение безопасных параметров проходит через
draft → validation → activation, а не редактирует active version напрямую.

| Категория | Значение в этом проекте |
|---|---|
| `CODE_INVARIANT` | Структура предметной модели, calculation capabilities и security boundaries; меняются только кодом. |
| `CONFIGURABLE` | Безопасный параметр или binding в уже существующей capability; в будущем может попасть в module-owned runtime config. |
| `DATA` | Фактическая бизнес-информация, загружаемая source adapters или введённая вручную. |
| `SOURCE_CONFIGURATION` | Операционная настройка пути/маски/активного файла источника; не calculation rule. |
| `LEGACY_PARITY` | Подтверждённое Excel/Power Query поведение, которое нельзя «исправлять» без отдельного бизнес-решения. |

## Code invariants

| ID | Правило / граница | Текущее место | Почему `CODE_INVARIANT` |
|---|---|---|---|
| CI-01 | `Leg`: departure, arrival, aircraft, passengers; произвольное число плеч; один выбранный техстоп | `schemas.py`, `calculation.py`, React input | Это форма предметной сущности и user workflow, а не параметр расчёта. |
| CI-02 | Backend calculation engine — единственный источник формул; UI рендерит `details` | `calculation.py`, `CalculatorPage.tsx` | Single source of truth и API boundary требуют deploy при смене capabilities. |
| CI-03 | Состав компонентов и последовательность `route → fuel → ground → ANO → catering → VAT → M1/M2/M3` | `calculate_leg()` | Это структура модуля и результатный contract, а не свободная формула. |
| CI-04 | Обычное плечо и техстоп — две отдельные capability-ветки; форма результата M1/M2/M3 | `calculate_ground()` | Новая ветка/сущность или иной тип результата требует изменения кода модуля. |
| CI-05 | Типы canonical records, Pydantic response contract, диагностики и rounding contract | `records.py`, `schemas.py`, `calculation.py` | Гарантируют совместимость API/Excel; schema меняется только с deploy. |
| CI-06 | Атомарный lifecycle `stage → validate → activate`; upload size/XLSX validation | `sources.py`, `source_files.py` | Надёжность и security boundary не должны отключаться runtime-настройкой. |
| CI-07 | Whitelist variables/functions, запрет `eval`/`exec`/arbitrary I/O | `configuration/variables.py`, `configuration/functions.py`, строгая schema | Это обязательная code-owned security policy; Iteration 3 не добавляет evaluator строковых формул. |

## Configurable parameters and bindings

CF-01…CF-07 и безопасная часть CF-09 перенесены в typed baseline. Значения
поступают в существующие calculation/source capabilities через проверенную
модель; это ещё не independently persisted active runtime version.

| ID | Параметр / binding | Сейчас | Будущий безопасный scope |
|---|---|---|---|
| CF-01 | Норма расхода топлива `2.7` т/ч | `configuration.fuel`; используется `calculation.py` | Numeric parameter для существующего fuel primitive. |
| CF-02 | Маршрутная ставка АНО `1666.6` на 100 км | `configuration.ano` + operation parameter ref | Editable без deploy, trace показывает configuration origin. |
| CF-03 | Базовое питание: количество `6` и ставка `1500` | `configuration.catering` + operation parts | Numeric parameters и composition безопасных parts. |
| CF-04 | Доплата за пассажира `500` | `configuration.catering` + operation parts | Parameter существующей registered variable `passengers`. |
| CF-05 | НДС: ставка `0.1` и список DME/SVO/VKO | `configuration.vat` + conditional operation | Rate и airport set при сохранении typed condition boundary. |
| CF-06 | Числовые нормы НО: объёмы/делители, 90 минут телетрапа, транспортный порог 100, ставка пожарной машины `25132` | `configuration.ground`; используется code-owned ground block | Состав normal/techstop services остаётся invariant. |
| CF-07 | Aircraft multipliers и scenario M1/M2/M3 rates | `configuration.overrides` active Configuration v1 | Единственный production owner; validation и trace показывают versioned configuration origin. |
| CF-08 | Источник топлива, сценарий, включение пассажирского питания, выбранный techstop | `CalculationRequest` | Это per-calculation input, не active runtime config; их shape — invariant, а допустимый выбор опирается на data. |
| CF-09 | Source directory и file mask | `source_configs`/Settings UI; adapter identity — module definition | `SOURCE_CONFIGURATION`; не влияет на active calculation configuration напрямую. |
| CF-10 | Будущие active flags, priorities, effective dates и source mappings | отсутствуют | `DEFERRED` до отдельного lifecycle/mapping scope; не добавлять структуру заранее. |

## Business data

| ID | Набор данных | Physical source / текущий adapter | Использование |
|---|---|---|---|
| DT-01 | Тарифы SRV | `7480_srv*.xlsx` → `parse_srv_tariffs` | Ставки ГСМ, НО, АНО; physical row order сохраняется. |
| DT-02 | Ручные тарифы и legacy `ЦРТ+` | API/manual JSON + one-time `baselines/manual_tariffs.json` seed | Дополняют отсутствующие ключи и отображают conflict; workbook parser только DEV compatibility. |
| DT-03 | Цена топлива АК | `реестр*.xlsx` + курс ЦБ → `parse_fuel_registry` | Цена на аэропорт вылета для `fuel_source=АК`. |
| DT-04 | Маршрут: distance и flight time | `reference_data/defaults/routes.json` → active Reference version (500-row seed) | Lookup маршрута, топливо, АНО, margins; active snapshot immutable до activation следующей версии. |
| DT-05 | Признак международного аэропорта | `Признак МВЛ` → compatibility monitor adapter | DEV parity/migration only; production ВВЛ invariant не читает это значение. |
| DT-06 | Aircraft multiplier | Configuration v1 baseline overrides | Airport part АНО и связанные НО объёмы. |
| DT-07 | Scenario M1/M2/M3 rates | Configuration v1 baseline overrides | Margin по сценарию и типу ВС. |
| DT-08 | Other costs by airport | `reference_data/defaults/airport_other_costs.json` → active Reference version (45-row seed) | Строка `ПРОЧЕЕ` normal ground block; independent lifecycle не меняет live data revision. |
| DT-09 | Dataset identity, active/uploaded file, source status/audit | local `JsonStore` | Операционная метаинформация; не является бизнес-формулой. |

## Ownership matrix

| Operational value | Authoritative owner | Effective behavior |
|---|---|---|
| Fuel burn rate | `CONFIGURATION` | Versioned numeric parameter. |
| ANO route rate | `CONFIGURATION` | Versioned parameter referenced by ANO operation. |
| Catering parameters/composition | `CONFIGURATION` | Versioned typed parts and allowed operation order. |
| VAT and ground numeric parameters | `CONFIGURATION` | Versioned parameters; ground service matrix remains code-owned. |
| Aircraft multipliers | `CONFIGURATION` | Active Configuration v1 is the sole production owner. |
| Scenario M1/M2/M3 rates | `CONFIGURATION` | Active Configuration v1 is the sole production owner. |
| Fuel price and ground services | `DATA` | Canonical live/manual tariff dataset. |
| Routes and Airport Other Costs | `REFERENCE_DATA` | Active immutable version is calculation owner; checked-in seed fills fresh/empty store, populated legacy state migrates into v1 without overwrite. |
| Source masks and active files | `SOURCE_CONFIGURATION` | Source lifecycle only; not a calculation rule. |
| Lookup policy, registered variables/operations, DTO shape | `CODE_INVARIANT` | Deploy required to change capability boundary. |
| First-match, fallback, rounding sequence | `LEGACY_PARITY` | Preserved unless business methodology changes. |

## Legacy parity rules

| ID | Правило | Текущее место | Почему не менять без решения бизнеса |
|---|---|---|---|
| LP-01 | `VLOOKUP` first-match по `airport-service`; imported rows идут перед manual | `tariffs_for_view`, `build_tariff_index` | Дубли допустимы; порядок даёт Excel-совместимый результат. |
| LP-02 | При duplicate route берётся первая физическая строка | `resolve_leg_context()` | Повторяет поиск ИШР через ВПР. |
| LP-03 | Нормализация SRV: allowlist услуг/ВС; максимум керосина и AER-specific отбор | `parsers/tariffs.py` | Это точное текущее Power Query behaviour, не общий rule engine. |
| LP-04 | Route отсутствует → flight time/distance/margins 0, но остальные применимые компоненты остаются | `calculate_leg()` | Осознанно degraded calculation, не скрытая бизнес-поправка. |
| LP-05 | Missing fuel/tariff/ANO/multiplier/scenario даёт 0 + warning/diagnostic | `calculation.py` | Legacy result сохраняется, хотя теперь помечен `degraded`. |
| LP-06 | Недоступный CBR → `95 RUB/USD` | `parsers/fuel.py` | Утверждённый fallback; richer metadata/trace остаётся deferred. |
| LP-07 | Время Excel игнорирует секунды; monetary components round to 2 decimals после full-precision totals | parser/common, calculation/export | Результаты golden master зависят от этого порядка и точности. |
| LP-08 | Failed production refresh сохраняет active dataset; compatibility workbook payload не участвует в lifecycle | source lifecycle | SRV/Fuel activation atomic; не возвращать workbook dependency. |
| LP-09 | Worksheet names, column positions и `Прочее!27` bindings | compatibility monitor adapter | Physical Excel binding сохранён только для DEV parity/migration tooling. |

## Iteration 7 result and deferred decisions

- Schema `2.0` upgrades persisted v1 configurations in memory, preserving
  immutable stored history and rollback semantics.
- Runtime payload accepts only typed parts, registered variables/parameters,
  registered lookups and bounded operations. `eval`, `exec`, arbitrary Python,
  dynamic imports and arbitrary I/O are impossible by schema and validation.
- `EffectiveCalculationContext` resolves configuration-owned aircraft/scenario
  values and source tariffs with provenance; no active configuration value is
  silently ignored.
- Missing required ground tariffs retain legacy numeric zero and add
  `GROUND_TARIFF_MISSING`, making the result `degraded`.
- `/admin` exposes editing and lifecycle controls while `/` preserves normal
  Cost Monitor UX. Preview comparison shows active/draft/difference on the
  same input; compare reports semantic operation changes.
- CBR-derived fuel prices retain rate/source/timestamp/fallback metadata in
  canonical data and calculation trace.
- SQL Server, generic overrides for tariffs/fuel prices, a visual node editor,
  authentication/RBAC, second monitor and shared platform extraction remain
  `DEFERRED`.
