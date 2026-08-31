# Cost Monitor Configuration Inventory

## Статус и назначение

**Iteration:** 7 — Complete Configurable Calculation Architecture.
**Статус:** active configuration schema `2.0` содержит typed parameters,
operation parts, safe conditions/lookups и versioned source-derived overrides.
ANO, Catering и VAT выполняются через Cost Monitor-owned operation executor.
Отдельный `/admin` поддерживает Create Draft → Edit → Validate → Preview /
Compare → Activate и rollback; root Cost Monitor не содержит admin UI.

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
| CF-07 | Aircraft multipliers и scenario rates до первого refresh | module definition bootstrap data | Это DATA fallback, не active configuration. |
| CF-08 | Источник топлива, сценарий, включение пассажирского питания, выбранный techstop | `CalculationRequest` | Это per-calculation input, не active runtime config; их shape — invariant, а допустимый выбор опирается на data. |
| CF-09 | Source directory и file mask | `source_configs`/Settings UI; adapter identity — module definition | `SOURCE_CONFIGURATION`; не влияет на active calculation configuration напрямую. |
| CF-10 | Будущие active flags, priorities, effective dates и source mappings | отсутствуют | `DEFERRED` до отдельного lifecycle/mapping scope; не добавлять структуру заранее. |

## Business data

| ID | Набор данных | Physical source / текущий adapter | Использование |
|---|---|---|---|
| DT-01 | Тарифы SRV | `7480_srv*.xlsx` → `parse_srv_tariffs` | Ставки ГСМ, НО, АНО; physical row order сохраняется. |
| DT-02 | Ручные тарифы и legacy `ЦРТ+` | API/manual JSON и sheet `ЦРТ+` → monitor adapter | Дополняют отсутствующие ключи и отображают conflict. |
| DT-03 | Цена топлива АК | `реестр*.xlsx` + курс ЦБ → `parse_fuel_registry` | Цена на аэропорт вылета для `fuel_source=АК`. |
| DT-04 | Маршрут: distance и flight time | sheet `ИШР` → monitor adapter | Lookup маршрута, топливо, АНО, margins. |
| DT-05 | Признак международного аэропорта | sheet `Признак МВЛ` → monitor adapter | Определяет МВЛ/ВВЛ. |
| DT-06 | Aircraft multiplier | sheet `Справочники!F:G` → monitor adapter | Airport part АНО и связанные НО объёмы. |
| DT-07 | Scenario M1/M2/M3 rates | sheet `Справочники!L:P` → monitor adapter | Margin по сценарию и типу ВС. |
| DT-08 | Other costs by airport | sheet `Прочее`, строка 27 → monitor adapter | Строка `ПРОЧЕЕ` normal ground block. |
| DT-09 | Dataset identity, active/uploaded file, source status/audit | local `JsonStore` | Операционная метаинформация; не является бизнес-формулой. |

## Ownership matrix

| Operational value | Authoritative owner | Effective behavior |
|---|---|---|
| Fuel burn rate | `CONFIGURATION` | Versioned numeric parameter. |
| ANO route rate | `CONFIGURATION` | Versioned parameter referenced by ANO operation. |
| Catering parameters/composition | `CONFIGURATION` | Versioned typed parts and allowed operation order. |
| VAT and ground numeric parameters | `CONFIGURATION` | Versioned parameters; ground service matrix remains code-owned. |
| Aircraft multipliers | `DATA` | Workbook dataset, optionally replaced by explicit `CONFIGURATION` override. |
| Scenario M1/M2/M3 rates | `DATA` | Workbook dataset, optionally replaced by explicit `CONFIGURATION` override. |
| Fuel price, route, ground services | `DATA` | Canonical dataset from source/manual tariff policy. |
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
| LP-08 | Пустой workbook section очищает прошлые values; failed full refresh сохраняет active dataset | source lifecycle | Reliability invariant, введённый в Iteration 1; не возвращать старое sticky/partial behaviour. |
| LP-09 | Worksheet names, column positions и `Прочее!27` bindings | monitor/SRV/fuel adapters | Physical Excel binding; позднее может стать validated source mapping, сейчас не менять без adapter scope. |

## Iteration 7 result and deferred decisions

- Schema `2.0` upgrades persisted v1 configurations in memory, preserving
  immutable stored history and rollback semantics.
- Runtime payload accepts only typed parts, registered variables/parameters,
  registered lookups and bounded operations. `eval`, `exec`, arbitrary Python,
  dynamic imports and arbitrary I/O are impossible by schema and validation.
- `EffectiveCalculationContext` resolves configuration, source data and only
  two targeted override families with provenance; no active configuration value
  is silently ignored.
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
