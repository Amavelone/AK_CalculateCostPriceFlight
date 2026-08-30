# AK_CalculateCostPriceFlight
## Базовая архитектурная спецификация и техническое задание на следующий этап развития

**Версия документа:** 1.0  
**Дата:** 30.08.2026  
**Назначение:** единый человеческий источник требований для последующей подготовки GPT Prompt Master и серии запросов к Codex.  
**Основа:** архитектурное видение v2, аудит кода/рефакторинга/библиотек и последующие уточнения архитектурной модели в обсуждении.

---

## Содержание

1. Назначение документа и способ использования
2. Коротко: что строится и зачем
3. Текущее состояние и отправная точка
4. Неприкосновенные инварианты
5. Архитектурная модель: платформа, модуль, конфигурация
6. Платформенный слой
7. Модульный слой и Cost Monitor как reference module
8. Конфигурационный слой
9. Данные: physical source, adapter, canonical contract
10. Source и Storage как разные понятия
11. Calculation Engine, diagnostics и trace
12. Административный контур
13. API как общий интерфейс аналитической платформы
14. Архитектура кода и инженерные принципы
15. SOLID применительно к проекту
16. DRY, KISS, YAGNI и дополнительные правила
17. Аудит текущей реализации: сильные стороны
18. Аудит текущей реализации: реальные проблемы
19. Целевой рефакторинг backend
20. Целевой рефакторинг frontend
21. Сторонние библиотеки и инструменты
22. Pandas, OpenPyXL и табличный слой
23. Тестовая стратегия и Excel parity
24. Надёжность данных и жизненный цикл источников
25. Безопасность
26. Документация, Git и правила работы Codex
27. Эволюционный roadmap
28. Что сознательно не делаем сейчас
29. Критерии готовности следующей архитектурной версии
30. Требования к будущему GPT Prompt Master
31. Итоговые архитектурные решения
32. Приложения: чек-листы и матрицы решений

---

# 1. Назначение документа и способ использования

Этот документ не является ни README, ни стенограммой обсуждения, ни готовым prompt для Codex. Его задача - стать **единым техническим заданием человеческого уровня**, от которого дальше можно последовательно строить несколько точных prompts для Codex и других инженерных агентов.

Документ объединяет два ранее раздельных направления:

1. **Глобальную архитектуру сервиса** - каким должен стать сам сервис аналитических мониторов, где проходит граница платформы, модуля, конфигурации, источников, API, хранения и будущих интеграций.
2. **Архитектуру и качество кода** - как должен быть организован production-код внутри этих границ, какие рефакторинги оправданы, какие библиотеки снимают рутину, какие инженерные принципы применяются и где проходит граница между хорошей структурой и overengineering.

Документ должен использоваться в следующей последовательности:

```text
Человек формулирует и уточняет архитектурные цели
                ↓
Этот документ фиксирует цели, границы и критерии
                ↓
GPT Prompt Master превращает документ в исполнимый prompt
                ↓
Codex выполняет работу по отдельным итерациям
                ↓
Tests / golden master / diff подтверждают сохранение поведения
                ↓
PROJECT_INDEX / PROJECT_CHANGELOG / architecture docs обновляются
```

Главная идея - не заставлять Codex одновременно угадывать архитектуру, придумывать требования, менять код и проверять результат. Сначала фиксируется архитектурная модель, затем из неё делаются отдельные управляемые технические итерации.

---

# 2. Коротко: что строится и зачем

Текущий Cost Monitor уже работает как MVP: расчёты сходятся с исходным Excel, пользовательские ручки и справочники работают, источники подключаются, а backend и frontend физически разделены. Следующая цель - не переделать рабочий монитор ради красоты, а превратить его в **первый эталонный модуль будущего внутреннего аналитического сервиса**.

Целевая формулировка архитектуры:

> **Модульная аналитическая платформа с единым инфраструктурным ядром, независимыми предметными модулями и конфигурируемой расчётной логикой.**

Это не ERP, не классическая микросервисная система, не универсальная low-code платформа и не коммерческий конструктор. Это локальная корпоративная аналитическая платформа для собственного департамента, которая работает с уже существующими данными компании, преобразует их внутри аналитического контекста и выдаёт расчёты, мониторинг и позднее - отчёты/дашборды/автоматизации.

Главный продуктовый принцип:

> **Сложность - для архитектуры и администратора, а не для пользователя.**

Обычный пользователь по-прежнему должен видеть простой монитор: выбрать или ввести параметры, получить результат, при необходимости раскрыть детализацию. Конфигурации, версии правил, source mappings, trace, сравнение версий и rollback существуют отдельно в административном контуре.

![Целевая модель ответственности](assets/01_layers.png)

---

# 3. Текущее состояние и отправная точка

Последняя foundation-версия уже сделала важный шаг от случайного pet-project к небольшому модульному монолиту.

Концептуально текущий backend уже организован вокруг отдельного Cost Monitor feature:

```text
backend/app/
  main.py                       # composition root FastAPI
  core/
    config.py                   # runtime/environment
  modules/
    cost_monitor/
      api.py                    # feature API
      schemas.py                # request/response contracts
      records.py                # typed canonical calculation records
      calculation.py            # calculation source of truth
      catalog.py                # tariff semantics
      exports.py                # JSON/XLSX exports
      sources.py                # source refresh orchestration
      source_files.py           # upload / preview / files
      parsers/
        common.py
        tariffs.py
        fuel.py
        monitor.py
      store.py                  # local JSON persistence
```

Frontend также уже сгруппирован feature-oriented:

```text
frontend/src/
  App.tsx
  features/
    cost-monitor/
      CostMonitorApp.tsx
      api.ts
      types.ts
      formatting.ts
      pages/
        CalculatorPage.tsx
        SourcesPage.tsx
        TariffsPage.tsx
        SettingsPage.tsx
```

Это **не нужно снова глобально перестраивать только ради нового дерева папок**. Уже сделанное нужно считать foundation, а дальнейшую работу вести через реальные seams: типы, контракты, конфигурацию, source lifecycle, execution trace, diagnostics, storage boundaries и админский контур.

Самые важные свойства текущей базы, которые необходимо сохранить:

- `calculate(state, request)` не зависит от React и UI;
- calculation engine не должен зависеть от файловой системы или FastAPI;
- frontend не является источником итоговой расчётной логики;
- парсеры отделены от calculation engine;
- physical first-match поведения, важные для Excel parity, зафиксированы;
- существует golden-master контроль известных Excel-сценариев;
- проект остаётся одним deployable сервисом;
- не введены лишние микросервисы, DI containers, Redis, Celery и глобальные state frameworks.

---

# 4. Неприкосновенные инварианты

Все следующие архитектурные и кодовые изменения подчиняются принципу:

> **Preserve behavior first. Improve internals second.**

Для Cost Monitor внешнее поведение является контрактом. Без отдельного бизнес-решения нельзя менять:

- визуал пользовательского монитора;
- основной UX;
- набор и смысл пользовательских ручек;
- бизнес-методологию;
- последовательность существующих расчётов;
- формулы M1 / M2 / M3;
- алгоритмы ЦРТ / АК;
- техстоп;
- ВВЛ / МВЛ;
- НДС;
- rounding;
- first-match semantics;
- существующие публичные API contracts;
- экспортируемые значения;
- Excel parity.

Для одинакового валидного input:

```text
OLD components == NEW components
OLD totals     == NEW totals
OLD M1/M2/M3   == NEW M1/M2/M3
```

Если в процессе архитектурной работы обнаруживается странное legacy-правило, оно не исправляется автоматически. Оно получает статус `LEGACY_PARITY`, покрывается тестом и выносится как отдельное решение бизнеса.

Golden expected values нельзя генерировать текущим Python-калькулятором: иначе golden master перестаёт быть независимым эталоном.

---

# 5. Архитектурная модель: платформа, модуль, конфигурация

Фиксируются три уровня ответственности.

## 5.1. Платформа

Платформа отвечает за технические механизмы, которые могут быть общими для нескольких аналитических модулей. Она не должна знать, как считается конкретная себестоимость рейса.

## 5.2. Модуль

Модуль отвечает за конкретную аналитическую задачу. Сейчас reference module - `Cost Monitor`. В будущем возможны `Cargo Monitor`, `Production Cube Monitor` и другие, но их будущие детали нельзя угадывать заранее.

## 5.3. Runtime Configuration

Runtime-конфигурация отвечает на вопрос:

> Как именно этот конкретный модуль должен считать **сейчас**, в пределах уже разрешённой схемы и engine capabilities?

Именно этот слой возвращает оперативность Excel: изменяемые коэффициенты, bindings, формулы и приоритеты могут меняться без новой сборки приложения, но уже с validation, versioning, audit и rollback.

---

# 6. Платформенный слой

Платформа - не «общая папка со всем подряд». В неё попадает только то, что действительно не зависит от конкретного монитора и подтверждено хотя бы двумя сценариями использования либо является очевидно инфраструктурным механизмом.

Платформа потенциально отвечает за:

- composition root приложения;
- регистрацию модулей;
- API composition;
- общий framework source adapters;
- configuration service infrastructure;
- version storage;
- validation framework basics;
- generic diagnostics envelope;
- generic execution-trace envelope;
- audit events;
- persistence boundaries;
- storage adapters;
- lifecycle активных наборов данных;
- logging/observability;
- security/auth infrastructure в будущем;
- общие export capabilities только после реального повторного использования.

Платформа **не должна** знать:

- что такое M1/M2/M3;
- какие airport services существуют;
- как считается ANO;
- что такое расход топлива 2.7;
- какие airport codes участвуют в VAT;
- как Cost Monitor определяет техстоп;
- какие конкретные поля пользователь видит в блоке плеча.

Практическое правило:

> Если название класса/функции в platform содержит предметный термин Cost Monitor, нужно проверить, не протекает ли модульная логика в platform.

---

# 7. Модульный слой и Cost Monitor как reference module

Cost Monitor является первым эталонным модулем. Он владеет собственной предметной моделью и не должен быть превращён в абстрактный `BaseMonitor`, от которого все будущие модули обязаны наследоваться.

Модуль Cost Monitor определяет:

- пользовательские экраны;
- модель `Leg`;
- DEP / ARR / Aircraft / Passengers как input concepts;
- возможность добавлять/удалять плечи;
- понятие техстопа;
- форму результата;
- M1/M2/M3 как часть своего domain result;
- canonical data contract, который ему нужен;
- зарегистрированные переменные;
- разрешённые Cost Monitor calculation primitives;
- module-owned configuration schema;
- baseline configuration;
- Excel parity rules;
- module-specific validation;
- module-specific API/application capabilities;
- специфические операции, которые не являются generic platform concern.

Важно отличать **структуру сущности** от **настройки её поведения**.

Например:

```text
Leg
  departure
  arrival
  aircraft
  passengers
```

- само существование этих полей - код модуля;
- откуда берётся справочник aircraft - binding/source configuration;
- какой коэффициент применяется к aircraft - runtime config/data;
- новая сущность, которой раньше не существовало, - изменение кода модуля.

Shared abstractions создаются только по факту. До появления второго реального модуля запрещено строить `UniversalMonitor`, `BaseCalculator`, `UniversalFormulaEngine` и другие конструкции «на будущее».

---

# 8. Конфигурационный слой

Конфигурация не должна быть размазана небольшими кусками по всему production-коду. У каждого модуля должен быть явный configuration boundary.

Концептуальный subpackage:

```text
modules/cost_monitor/
  configuration/
    schema.py        # что вообще разрешено конфигурировать
    defaults.py      # baseline, эквивалент current behavior
    variables.py     # зарегистрированные переменные
    functions.py     # whitelist primitives/functions
    validation.py    # type/dependency/security validation
```

Это не обязательная буквальная структура. KISS важнее количества файлов.

## 8.1. Configuration Definition

Редко меняется и находится в коде:

- schema;
- типы;
- зарегистрированные variables;
- allowed operators;
- allowed functions;
- component capabilities;
- safety constraints;
- structural invariants.

Изменение definition требует deploy.

## 8.2. Runtime Configuration

Может изменяться администратором без redeploy:

- коэффициенты;
- numeric parameters;
- formula expressions в пределах schema;
- lookup bindings;
- source mappings;
- priorities;
- active flags;
- даты действия;
- порядок/состав компонентов, если это разрешено definition;
- safe conditions.

## 8.3. Классификация каждого правила

Перед переносом в configuration любое правило должно получить категорию:

| Категория | Смысл | Пример |
|---|---|---|
| `CODE_INVARIANT` | меняется только через код | новая предметная сущность, новый тип результата |
| `CONFIGURABLE` | бизнес может менять без deploy | коэффициент 2.7, ставка, priority |
| `DATA` | приходит из источников/справочников | тариф, route, fuel price |
| `LEGACY_PARITY` | странное, но обязано сохраняться до решения | first-match, fallback, Excel-specific behavior |

## 8.4. Не «конструктор всего»

Первая configuration architecture - контролируемый calculation configuration, а не универсальная no-code система.

Запрещено:

```text
eval()
exec()
arbitrary Python
arbitrary imports
произвольные filesystem/network calls из конфигурации
```

Если понадобятся строковые formulas, допускается restricted evaluator: literals, арифметика, comparisons, boolean operations, зарегистрированные variables и whitelist functions.

---

# 9. Данные: physical source, adapter, canonical contract

Одно из ключевых архитектурных решений - модуль не должен зависеть от физической формы источника.

![Источники и канонический контракт](assets/02_data_contract.png)

Пример physical source:

```text
DEP_PORT
ARR_PORT
PAX_CNT
AC_TYPE
```

Canonical Cost Monitor contract:

```text
departure
arrival
passengers
aircraft
```

Binding:

```text
DEP_PORT -> departure
ARR_PORT -> arrival
PAX_CNT  -> passengers
AC_TYPE  -> aircraft
```

Binding относится к adapter/source configuration.

Если Excel с 10 колонками завтра заменяется SQL Server таблицей с 15 колонками, но canonical module contract тот же, Cost Monitor не должен меняться. Меняется source adapter и mapping.

Если появляется **новый бизнес-смысл**, которого раньше не было в модели, это уже изменение module contract и, следовательно, кодовая работа.

Для source/domain boundaries нужно постепенно переходить от `dict[str, Any]` к typed canonical records, например:

```text
RouteRecord
TariffRecord
FuelPriceRecord
AircraftMultiplier
ScenarioRate
SourceRunResult
```

Рекомендуемая граница:

```text
OpenPyXL / Pandas / SQL / API
            ↓
         Adapter
            ↓
      Normalization
            ↓
 Typed canonical records
            ↓
      Cost Monitor
```

---

# 10. Source и Storage как разные понятия

Эти понятия нельзя смешивать.

## 10.1. Source

Откуда приходят бизнес-данные:

- Excel;
- CSV;
- SQL Server;
- API;
- 1С;
- SOFI;
- внешний сервис.

## 10.2. Storage

Где сама платформа хранит собственное состояние:

- runtime configuration;
- versions;
- drafts;
- audit;
- active dataset metadata;
- future snapshots;
- calculation history;
- user/session state при необходимости.

Один модуль может получать данные из Excel, а другой - из SQL Server. Это нормальный сценарий.

`JsonStore` в текущей версии остаётся **официальным local MVP adapter**, а не временным «плохим кодом, который нужно немедленно удалить». Он должен быть изолирован так, чтобы позднее storage можно было заменить SQL Server реализацией без изменения calculation engine.

SQL Server - целевое корпоративное направление, но миграция не должна делаться раньше, чем стабилизированы contracts/config/versioning boundaries.

---

# 11. Calculation Engine, diagnostics и trace

Calculation Engine должен оставаться единственным источником бизнес-расчёта на backend. Frontend отображает результат и не повторяет формулы.

Целевая модель:

```text
CalculationRequest
      ↓
Module Context
      ↓
Active Configuration Version
      ↓
Calculation Engine
      ↓
Component Results
      ↓
Result + Diagnostics + Trace
```

![Calculation trace](assets/04_trace.png)

## 11.1. Декомпозиция `calculate_leg()`

Текущая крупная функция сама по себе не является ошибкой, если она остаётся когерентной. Её не нужно превращать в 15 классов.

Безопасная механическая декомпозиция может выглядеть так:

```text
calculate_leg
  -> resolve_context
  -> calculate_fuel_component
  -> calculate_ground_component
  -> calculate_ano_component
  -> calculate_catering_component
  -> calculate_vat_component
  -> calculate_margin_levels
```

Точные имена вторичны. Главное - сохранить линейную читаемость orchestration и порядок вычислений.

## 11.2. Structured Diagnostics

Текущий baseline допускает degraded calculations, которые выглядят как обычные цифры. Нельзя автоматически менять их бизнес-результат, если это Excel parity, но нужно сделать качество расчёта видимым.

Пример:

```text
status: complete | degraded

diagnostics:
  code
  severity
  component
  reference
  message
```

Старые `warnings` сохраняются для compatibility.

## 11.3. Calculation Trace

Trace должен объяснять не Python internals, а бизнес-цепочку:

```text
INPUT
 ↓
LOOKUP
 ↓
PARAMETERS
 ↓
FORMULA / OPERATION
 ↓
RESULT
```

Пример fuel:

```text
flight_time = 2.133333
fuel_rate = 2.7
fuel_tons = flight_time * fuel_rate
price source = CRT
result = ...
config_version = ...
```

Trace нужен для:

- отладки;
- объяснения результата бизнесу;
- сравнения versions;
- audit;
- migration parity;
- будущего API/n8n;
- admin visualization.

---

# 12. Административный контур

Гибкость должна существовать отдельно от основного пользовательского UX.

## 12.1. Пользователь

Видит:

- плечи;
- inputs;
- ручки;
- итог;
- понятную детализацию.

## 12.2. Администратор

Имеет отдельный раздел:

- sources;
- mappings;
- parameters;
- formulas/rules;
- versions;
- validation;
- compare;
- test calculation;
- activation;
- rollback;
- audit;
- trace.

## 12.3. Жизненный цикл изменения правила

![Жизненный цикл конфигурации](assets/03_config_lifecycle.png)

```text
ACTIVE v1
   ↓
CREATE DRAFT v2
   ↓
EDIT
   ↓
VALIDATE
   ↓
PREVIEW / CONTROL CALCULATION
   ↓
COMPARE
   ↓
ACTIVATE
   ↓
AUDIT
```

Rollback возвращает предыдущую immutable version.

Активная версия не редактируется напрямую.

Это позволяет вернуть оперативность Excel, но убрать его главный риск - тихое изменение методологии без истории и контроля.

---

# 13. API как общий интерфейс аналитической платформы

UI не должен быть единственным способом воспользоваться business logic.

Целевая модель:

```text
User UI ─────────┐
n8n ─────────────┤
Automated report ┤ -> Module Application/API -> Calculation Engine
Dashboard ───────┘
```

На текущем этапе Cost Monitor API может оставаться module-owned и сохранять compatibility routes.

В дальнейшем platform может давать единые правила API composition, authentication, audit, version metadata и module registration, но не должна скрывать предметный смысл каждого module capability.

Пример будущего n8n use case:

```text
input:
  DEP
  ARR
  Aircraft
  Passengers
  Settings

output:
  M1
  M2
  M3
  status
  config_version
  data_snapshot_id
```

Автоматизированные отчёты и dashboards в будущем должны быть **consumers одной и той же calculation/data logic**, а не новыми местами, где формулы копируются.

---

# 14. Архитектура кода и инженерные принципы

Глобальная архитектура отвечает на вопрос «где живёт ответственность». Архитектура кода - «как эта ответственность реализована внутри границы».

Для production-кода фиксируются следующие принципы:

- SOLID - ориентир для границ и зависимостей, а не повод создавать interface на каждую функцию;
- DRY - не дублировать бизнес-смысл, но не создавать абстракции после двух похожих строк;
- KISS - выбирать самое простое решение, которое сохраняет контракт и расширяемость;
- YAGNI - не строить generic capability до появления реального use case;
- Separation of Concerns;
- Single Source of Truth;
- explicit contracts over implicit dictionaries;
- composition over inheritance;
- dependency direction from infrastructure to domain boundaries, а не наоборот;
- observable failures вместо silent degradation;
- typed boundaries там, где тип реально защищает систему;
- documentation explains WHY, а не пересказывает WHAT.

---

# 15. SOLID применительно к проекту

SOLID используется прагматично.

## 15.1. S - Single Responsibility Principle

Файл/класс/функция должен иметь одну понятную причину для изменения.

Хорошие текущие примеры:

- parser files разделены по источникам;
- calculation отделён от HTTP;
- pages отделены от `CostMonitorApp`.

Плохие симптомы:

- endpoint одновременно парсит файл, меняет storage и считает бизнес-результат;
- React component повторяет backend formula;
- configuration storage знает Cost Monitor formula semantics.

SRP не означает «одна функция = пять строк».

## 15.2. O - Open/Closed Principle

Система должна позволять добавлять новые source adapters или config versions без переписывания calculation engine.

Но не нужно заранее создавать abstract base class для каждого будущего монитора.

## 15.3. L - Liskov Substitution Principle

Актуален прежде всего для adapters/storage implementations. Если `JsonConfigurationStorage` позднее заменяется `SqlServerConfigurationStorage`, application service не должен менять поведение.

Не следует искусственно применять наследование только ради LSP.

## 15.4. I - Interface Segregation Principle

Модуль должен зависеть от узких capability boundaries.

Например calculation не нужен весь `SourceManager`; ему нужен уже подготовленный canonical state/config.

## 15.5. D - Dependency Inversion Principle

Business calculation не должен зависеть от FastAPI, `openpyxl`, filesystem или SQL Server driver.

Правильное направление:

```text
Infrastructure implementation
        ↓
Adapter / boundary
        ↓
Module application/domain
```

DIP не требует DI-container. Явной композиции и FastAPI `Depends` достаточно.

---

# 16. DRY, KISS, YAGNI и дополнительные правила

## 16.1. DRY

Не дублировать **знание**.

Критичный пример: ANO/catering/VAT formulas не должны одновременно жить в Python и React.

Но DRY не означает выносить каждую похожую пару строк в helper. Слишком ранняя абстракция хуже локального повторения.

## 16.2. KISS

Предпочитать:

```text
явная функция + typed model
```

вместо:

```text
generic framework + registry + factory + meta-class
```

если второй вариант пока не даёт измеренной пользы.

## 16.3. YAGNI

Не реализовывать сейчас:

- universal rule engine;
- second-monitor abstractions до второго монитора;
- message broker;
- Redis;
- microservices;
- drag-and-drop builder;
- сложный approval workflow.

## 16.4. Single Source of Truth

- расчётные формулы - backend;
- активная configuration version - configuration service;
- canonical data - adapter output contract;
- test expected values - независимые fixtures/golden data.

## 16.5. Explicit over implicit

Предпочитать:

```text
TariffRecord.airport
```

вместо:

```text
row["АП"]
```

на внутренних границах модуля.

## 16.6. Evolutionary Architecture

Не проектировать идеальную платформу в вакууме.

```text
Cost Monitor
 ↓
первый конфигурационный механизм
 ↓
второй реальный module
 ↓
выделение действительно shared механизмов
```

---

# 17. Аудит текущей реализации: сильные стороны

Текущую foundation-ветку не следует считать плохой или требующей полного rewrite.

Сильные стороны:

1. **Feature boundary уже существует.** Cost Monitor физически собран как отдельный module/feature.
2. **Calculation source of truth выделен.** Это даёт возможность безопасного testing/refactoring.
3. **Парсеры разделены.** Нет необходимости дробить их дальше ради формального SOLID.
4. **Frontend страницы вынесены.** Есть seam для дальнейшей feature growth.
5. **Golden master - главный актив проекта.** Архитектурные изменения можно проверять по числам, а не по ощущениям.
6. **Нет overengineering.** Пока отсутствуют микросервисы, DI container, Redis, Redux, generic enterprise frameworks.
7. **JsonStore реализован аккуратно для локального MVP.** Atomic replace, locking и deep copy полезны в рамках одного процесса.
8. **OpenPyXL соответствует текущим Excel-parity требованиям.** Его использование не является техническим долгом само по себе.

---

# 18. Аудит текущей реализации: реальные проблемы

Ниже только проблемы, которые влияют на correctness, auditability, поддержку или масштабирование.

## 18.1. Неполный расчёт может выглядеть нормальным — resolved in Iteration 1

Отсутствующая ground-service ставка может превращаться в `0.0`, а итог продолжает выглядеть как полноценный calculation.

Сохранены baseline numbers и legacy `warnings`; API теперь также возвращает
`status: complete | degraded` и structured diagnostics.

## 18.2. Missing route даёт частичный финансовый результат — resolved in Iteration 1

При отсутствии ИШР flight time/distance/margin могут стать нулём, но часть ground/catering остаётся. Это legacy-compatible behavior и теперь маркируется как `degraded` diagnostic.

## 18.3. `refresh-all` публикует partial success — resolved in Iteration 1

Нельзя активировать смесь:

```text
new SRV + old Fuel + new Workbook
```

как один новый dataset revision.

Реализовано `stage -> validate -> atomic activate`: при ошибке хотя бы одного source активный dataset и его revision сохраняются.

## 18.4. Sticky workbook configuration — resolved in Iteration 1

Пустые валидные `aircraft_multipliers` или `scenario_rates` заменяют предыдущие значения и покрыты regression test.

## 18.5. `data_revision` не является snapshot

Счётчик версии полезен, но не позволяет восстановить исторический набор данных. На следующем этапе нужен seam для будущего immutable snapshot id; SQL-backed history - позже.

## 18.6. JsonStore не масштабируется на shared multi-process use

`RLock` работает только в одном процессе. Несколько workers могут привести к lost update. До перехода в shared deployment это допустимо; расширять JsonStore в «самодельную production DB» не нужно.

## 18.7. Слабая типизация response contracts — resolved in Iteration 1

Большие `dict[str, Any]` повышают риск тихого расхождения FastAPI/OpenAPI/TypeScript.

`CalculationResponse` стал явным OpenAPI/Pydantic contract и покрыт contract test; внутренние тарифы, цены и маршруты представлены immutable canonical records.

## 18.8. Frontend повторяет бизнес-формулы — resolved in Iteration 1

React рендерит backend `details` для всех компонентов; локальные формулы ANO/catering/VAT удалены.

## 18.9. Race condition calculation requests — resolved in Iteration 1

`AbortController` вместе с monotonic request id не позволяет старому response перезаписать актуальный result.

## 18.10. CBR fallback недостаточно прозрачен

`95.0` как legacy fallback может оставаться, но result должен знать `rate_source`, `fallback_used`, timestamp/quality metadata.

## 18.11. Upload validation минимальна — resolved in Iteration 1

Добавлены max size 25 МБ, безопасное имя и проверка фактически открываемого XLSX до публикации файла.

## 18.12. Raw preview может показать не active file — resolved in Iteration 1

Состояние source хранит отдельные `uploaded_file` и `active_file`; raw preview использует активированный файл.

---

# 19. Целевой рефакторинг backend

Backend-рефакторинг должен идти небольшими безопасными шагами.

## 19.1. Typed canonical records

Убрать наиболее критичные `dict[str, Any]` на parser -> module boundary.

Не нужно типизировать абсолютно всё в один commit.

## 19.2. Explicit response DTO

Requests и responses должны иметь явный contract. Pydantic используется на API/config boundaries; internal domain может использовать `dataclass`.

## 19.3. Calculation decomposition

Разделять крупную функцию по компонентам только механически и только если тесты подтверждают parity.

## 19.4. Network adapters

CBR request должен быть отделён от parser semantics и иметь testable HTTP client.

## 19.5. Source activation lifecycle

```text
read
parse
stage
validate
activate
```

Active state изменяется атомарно.

## 19.6. Persistence boundaries

Calculation engine получает state/config через application boundary, а не читает JSON напрямую.

---

# 20. Целевой рефакторинг frontend

Frontend не должен становиться сложнее ради будущей платформы.

Приоритеты:

1. убрать повторение backend calculation formulas;
2. сохранить существующий visual/UX;
3. защитить result от stale responses;
4. не добавлять Redux/Zustand без реальной проблемы;
5. выносить hooks только когда появилась самостоятельная ответственность;
6. admin UI держать отдельно от user flow;
7. `CostMonitorApp.tsx` дробить только по реальным capability boundaries.

Правильная модель:

```text
Component
  ↓ events
State / application hook
  ↓
API client
  ↓
Backend result
  ↓
Render
```

Business formulas во frontend отсутствуют.

---

# 21. Сторонние библиотеки и инструменты

Библиотека добавляется, если она снимает реальную инфраструктурную рутину лучше, чем небольшой собственный код. Нельзя добавлять пакет только потому, что он популярен.

## 21.1. Уже сейчас: Ruff

Назначение:

- lint;
- import hygiene;
- unused imports;
- базовые code smells.

Не использовать как повод массово переформатировать весь repository.

## 21.2. При расширении environment config: `pydantic-settings`

Даст typed environment settings, validation и подготовит clean boundary для будущих DB/auth/source-root parameters.

## 21.3. Для внешнего HTTP: `httpx`

Подходит для CBR и будущих API adapters:

- timeout;
- явные exceptions;
- mock transport;
- единый HTTP client.

## 21.4. При реальной миграции SQL Server

Тогда, а не заранее:

- SQLAlchemy 2.x;
- `pyodbc`;
- Alembic.

SQLAlchemy нужен не ради ORM на каждую сущность, а ради transactions, pooling и стабильной data-access boundary.

## 21.5. Позже, при измеренной необходимости

- `tenacity` - retry/backoff при нескольких нестабильных network sources;
- `structlog` - structured contextual logging перед shared deployment;
- `pytest` - новые сложные fixtures/parametrization, без big-bang rewrite старого unittest suite;
- `pandera` - только если DataFrame становится реальной границей source normalization.

## 21.6. Не добавлять сейчас

- DI container;
- Celery/Redis;
- microservices;
- Redux/Zustand;
- universal rule-engine;
- full Pandas rewrite.

---

# 22. Pandas, OpenPyXL и табличный слой

Pandas не является автоматическим улучшением текущих parsers.

OpenPyXL сейчас уместен, потому что:

- важен physical row order;
- first-match parity критична;
- `read_only=True` экономит память;
- текущая логика в основном row-oriented;
- объёмы не требуют DataFrame любой ценой.

Pandas стоит вводить для конкретных workloads:

- join;
- groupby;
- pivot;
- массовые column transforms;
- reconciliation нескольких таблиц;
- профилирование.

Правильная граница:

```text
Pandas/OpenPyXL
      ↓
source adapter / normalization
      ↓
typed canonical records
      ↓
calculation domain
```

Не делать:

```text
DataFrame -> вся бизнес-логика системы
```

Polars имеет смысл только при действительно больших columnar workloads.

---

# 23. Тестовая стратегия и Excel parity

Тесты - не последняя стадия после рефакторинга, а инструмент управления самим рефакторингом.

## 23.1. Golden Master

Для утверждённых input sets:

```text
known input
   ↓
Excel expected values
   ↓
Python calculation
   ↓
component-by-component comparison
```

Контролируются не только totals, но и ключевые компоненты.

## 23.2. Обязательные категории тестов

- golden/parity;
- parser/source normalization;
- canonical contracts;
- API response contracts;
- diagnostics;
- missing references;
- atomic source activation;
- config validation;
- config version activation/rollback;
- trace consistency;
- CBR adapter/fallback metadata;
- raw preview active file;
- frontend typecheck/build;
- stale request protection, если есть frontend test setup.

## 23.3. Validation gate

Перед merge/релизом:

```text
Backend tests       PASS
Golden parity       PASS
API contract        PASS
Config tests        PASS
Ruff                PASS
Frontend typecheck  PASS
Frontend build      PASS
```

Если проверка технически не запускалась, статус `NOT RUN`, а не выдуманный PASS.

---

# 24. Надёжность данных и жизненный цикл источников

Важнейшее правило будущего shared deployment:

> Calculation не должен работать на случайной смеси поколений источников.

Целевой lifecycle:

```text
LOAD
 ↓
PARSE
 ↓
STAGE CANDIDATE
 ↓
VALIDATE
 ↓
ATOMIC ACTIVATE
```

Если один обязательный source невалиден, active dataset остаётся прежним.

`data_revision` сейчас можно оставить, но application boundary должен позволять позднее заменить его immutable `dataset_snapshot_id`.

Historical snapshots не нужно моделировать в JSON как полноценную БД. Этот функционал логично реализовать после SQL Server persistence.

---

# 25. Безопасность

Полноценный pentest сейчас не нужен, но архитектура не должна создавать очевидно опасные точки.

## 25.1. Configuration security

- no `eval`;
- no `exec`;
- no arbitrary imports;
- whitelist variables/functions;
- schema validation before activation;
- immutable active versions;
- size limits;
- draft isolation.

## 25.2. Source/upload security

- safe filename;
- max upload size;
- XLSX must really open;
- invalid upload cannot become active;
- allowed source roots перед shared deployment;
- не отдавать произвольный filesystem через API.

## 25.3. Network/shared deployment

До размещения для многих пользователей потребуется:

- authentication;
- RBAC;
- admin/user separation;
- structured audit;
- secrets management;
- proper storage concurrency;
- path restrictions.

Но эти вещи не нужно тащить в локальный MVP раньше времени.

---

# 26. Документация, Git и правила работы Codex

В проекте документы - часть архитектуры, а не постфактум-описание.

## 26.1. `PROJECT_INDEX.md`

Короткая навигационная карта для человека и AI.

При каждом новом запросе Codex сначала читает её, затем открывает только релевантные части кода.

Обновляется только при фактическом изменении paths/responsibilities.

## 26.2. `PROJECT_CHANGELOG.md`

Фиксирует значимые изменения:

- architecture;
- contracts;
- calculation;
- data/source lifecycle;
- frontend structure;
- dependencies;
- tests;
- security.

Не должен превращаться в копию `git log`.

## 26.3. Canonical Architecture Document

Должен быть один основной architecture document. Не создавать новые vision-файлы с дублирующим назначением после каждого этапа.

## 26.4. Git workflow

Большая архитектурная инициатива работает в отдельной feature branch.

Codex перед изменениями обязан:

```text
git branch --show-current
git status
git remote -v
```

Если working tree dirty, автоматический reset запрещён.

После задачи:

- tests;
- diff review;
- docs;
- commit;
- push;
- без самостоятельного merge в `main`.

---

# 27. Эволюционный roadmap

![Эволюционный roadmap](assets/05_roadmap.png)

## Этап 0 - Foundation: уже выполнен

- Cost Monitor feature boundary;
- parser split;
- frontend pages;
- calculation source of truth;
- golden master.

## Этап 1 - Code Foundation: реализован в Iteration 1

- typed canonical source/domain contracts;
- explicit response DTO;
- structured diagnostics;
- atomic source activation;
- remove frontend formula duplication;
- stale request protection;
- Ruff;
- `pydantic-settings` deferred: два существующих path settings остаются простой typed dataclass без измеренной необходимости нового package;
- httpx CBR adapter;
- upload/preview safety.

## Этап 2 - Configuration Inventory: реализован в Iteration 2

Для каждого правила:

```text
CODE_INVARIANT / CONFIGURABLE / DATA / LEGACY_PARITY
```

Результат зафиксирован в `docs/COST_MONITOR_CONFIGURATION_INVENTORY.md`.
Никакой configuration engine, baseline runtime config или admin UI на этом
этапе не добавляются.

## Этап 3 - Typed Configuration Model: реализован в Iteration 3

- module-owned schema;
- baseline config;
- registered variables;
- allowed primitives;
- validation.

Реализован строгий code-owned definition и baseline, воспроизводящий текущие
Python/Excel параметры. Calculation engine принимает validated configuration,
но по умолчанию использует baseline. Произвольный код и строковый evaluator не
добавлены. Configuration service, versions, activation, rollback и trace
остаются scope Этапа 4.

## Этап 4 - Configuration Service + Versioning + Trace

- active version;
- draft;
- validation;
- compare;
- activation;
- rollback;
- audit;
- calculation trace.

## Этап 5 - Admin Contour

Сначала read-only:

- active config;
- versions;
- trace;
- validation status.

Потом редактирование безопасных parameters/bindings.

## Этап 6 - Formal Adapters / SQL Readiness

- canonical contracts окончательно закреплены;
- source bindings формализованы;
- storage abstractions готовы к SQL Server.

## Этап 7 - SQL Server Persistence

- configuration versions;
- snapshots;
- audit;
- history;
- shared state.

Только здесь уместны SQLAlchemy/pyodbc/Alembic.

## Этап 8 - Второй реальный модуль

Добавить следующий monitor и проверить, какие механизмы действительно shared.

Только после этого поднимать повторяющиеся элементы в platform/shared.

---

# 28. Что сознательно не делаем сейчас

Чтобы сохранить управляемость проекта, в ближайшие итерации не нужно реализовывать:

- microservices;
- Redis;
- Celery;
- Kafka;
- message broker;
- dependency injection container;
- full DDD framework;
- generic low-code platform;
- drag-and-drop formula builder;
- arbitrary Python config;
- полноценную SQL Server migration раньше времени;
- глобальный Pandas rewrite;
- Redux/Zustand;
- Cargo Monitor до стабилизации Cost Monitor architecture;
- Production Cube Monitor до стабилизации Cost Monitor architecture;
- dashboards как самостоятельный calculation source;
- reports с дублированием формул;
- сложную RBAC/auth систему до shared deployment.

Это не означает «никогда». Это означает **не сейчас**, пока нет измеренной необходимости.

---

# 29. Критерии готовности следующей архитектурной версии

Следующую крупную архитектурную версию можно считать успешной, если одновременно выполнены следующие условия.

## 29.1. Поведение

- Cost Monitor визуально и функционально не изменился для пользователя;
- Excel golden master проходит;
- M1/M2/M3 совпадают;
- API compatibility сохранена.

## 29.2. Код

- критические `dict[str, Any]` boundaries заменены typed contracts;
- frontend не повторяет backend formulas;
- calculation orchestration читаемо;
- external HTTP отделён;
- source activation не публикует partial state;
- response DTO явны.

## 29.3. Архитектура

- существует явная граница platform/module/config;
- configuration inventory зафиксирован;
- module-owned configuration schema существует или подготовлена;
- JsonStore остаётся local adapter, но calculation от него не зависит напрямую;
- canonical data contract source-agnostic.

## 29.4. Надёжность

- degraded result технически различим;
- source/config validation происходит до activation;
- active revision/version имеет понятную identity;
- stale frontend result не может перезаписать новый.

## 29.5. Инженерный процесс

- tests/lint/typecheck/build являются gate;
- PROJECT_INDEX актуален;
- PROJECT_CHANGELOG актуален;
- architecture docs обновляются без дублирования;
- Git history понятна.

---

# 30. Требования к будущему GPT Prompt Master

Следующий GPT Prompt Master должен превратить этот документ не в один гигантский «сделай всё» запрос, а в **последовательность управляемых итераций**.

Каждая итерация должна содержать:

## 30.1. Контекст

- какая ветка является baseline;
- какие документы читать первыми;
- какие invariants неприкосновенны.

## 30.2. Scope

Чётко: что входит и что не входит.

## 30.3. Анализ до изменения

- current tree;
- current contracts;
- current tests;
- dirty working tree check.

## 30.4. Пошаговая реализация

Codex должен выполнять небольшими блоками и после каждого большого блока запускать релевантные tests.

## 30.5. Safety gates

- no behavior change;
- no golden regeneration;
- no force reset;
- no secrets;
- no build artifacts;
- no opportunistic refactoring вне scope.

## 30.6. Documentation update

Обновлять только документы, которые реально изменились.

## 30.7. Git

- отдельная/указанная branch;
- meaningful commit;
- push;
- no automatic merge.

## 30.8. Final report

Codex обязан вернуть:

```text
baseline
implemented
behavior parity
tests
docs updated
deferred
git commit/push
remaining risks
```

## 30.9. Почему работа должна быть итеративной

Первый prompt - укрепляет code foundation.

Второй - внедряет configuration architecture.

Следующие prompts - versioning, trace, admin UI, adapters, SQL persistence.

Так проще локализовать regressions и понять, какой архитектурный шаг действительно принёс пользу.

---

# 31. Итоговые архитектурные решения

Ниже решения, которые считаются принятыми основами до отдельного пересмотра.

1. Проект развивается как **модульный монолит**, а не микросервисы.
2. Целевая модель - **модульная аналитическая платформа**.
3. Основные уровни - **Platform / Module / Runtime Configuration**.
4. Cost Monitor - первый reference module.
5. Пользовательский UX не усложняется из-за конфигурации.
6. Configuration доступна только в административном контуре.
7. Изменение runtime rules в пределах schema не должно требовать deploy.
8. Active configuration имеет immutable version.
9. Calculation result должен знать config version и active data identity.
10. Calculation trace - обязательный элемент прозрачной архитектуры.
11. Frontend не является источником business formulas.
12. Module работает через canonical data contracts.
13. Physical Excel/SQL fields принадлежат adapters и mappings.
14. Source и Storage - разные слои.
15. JsonStore остаётся допустимым local adapter текущей версии.
16. Целевое shared storage направление - SQL Server, но не раньше готовности contracts/config model.
17. Shared abstractions создаются после второго реального use case.
18. SOLID используется прагматично; KISS/YAGNI имеют приоритет над академической чистотой.
19. DRY применяется к бизнес-знанию, а не к каждой похожей строке.
20. Third-party libraries вводятся точечно и по измеренной пользе.
21. Excel golden master остаётся эталоном до официального изменения методологии.
22. Big-bang rewrite запрещён: архитектура развивается эволюционно.

---

# 32. Приложения: чек-листы и матрицы решений

## 32.1. Где должно жить новое изменение

| Вопрос | Если ответ «да» | Уровень |
|---|---|---|
| Меняется сущность или user workflow? | нужен deploy | Module code |
| Меняется безопасный коэффициент/формула в существующей schema? | без deploy | Runtime config |
| Меняется физическая колонка/источник, canonical meaning тот же? | mapping/adapter | Source config |
| Появился новый storage backend? | implementation swap | Platform/storage |
| Механизм повторился минимум в двух модулях? | можно обобщить | Platform/shared |
| Нужно новое правило только Cost Monitor? | не поднимать наверх | Cost Monitor |

## 32.2. Матрица библиотек

| Инструмент | Сейчас | Позже | Причина |
|---|---:|---:|---|
| Ruff | Да | - | дешёвый quality gate |
| pydantic-settings | Да/при расширении config | - | typed environment |
| httpx | Да для CBR adapter | - | timeout/mock/errors |
| Pandas | Только по задаче | Да | joins/groupby/pivot |
| SQLAlchemy 2.x | Нет | Да при SQL Server | transactions/pooling |
| pyodbc | Нет | Да при SQL Server | driver |
| Alembic | Нет | Да при SQL Server | migrations |
| tenacity | Нет | Возможно | несколько network sources |
| structlog | Нет | Перед shared deploy | contextual logging |
| pytest | Не мигрировать всё | Постепенно | fixtures/parametrize |
| DI container | Нет | Скорее нет | явная композиция достаточна |
| Redis/Celery | Нет | Только по измерению | operational need first |

## 32.3. Чек-лист «не сломали ли мы Cost Monitor»

Перед каждым архитектурным commit:

- [ ] Golden master PASS
- [ ] Все backend tests PASS
- [ ] API contract tests PASS
- [ ] Frontend typecheck PASS
- [ ] Frontend build PASS
- [ ] Ruff PASS
- [ ] M1/M2/M3 unchanged
- [ ] Key component values unchanged
- [ ] User UI unchanged
- [ ] Existing API URLs unchanged
- [ ] No secrets / `.env` / source Excel in diff
- [ ] No unexpected `store.json` runtime changes
- [ ] PROJECT_INDEX updated only if needed
- [ ] PROJECT_CHANGELOG updated
- [ ] Deferred decisions documented, not silently «fixed»

## 32.4. Чек-лист новой runtime configuration rule

- [ ] Rule укладывается в existing schema
- [ ] Не требует новой предметной сущности
- [ ] Тип входов известен
- [ ] Все variables зарегистрированы
- [ ] Все functions whitelist-нуты
- [ ] Нет arbitrary code
- [ ] Validation проходит
- [ ] Есть контрольный calculation preview
- [ ] Compare с active version понятен
- [ ] Есть новая immutable version
- [ ] Есть rollback path
- [ ] Trace показывает использованное правило

## 32.5. Чек-лист новой shared abstraction

Перед тем как переносить механизм из module в platform:

- [ ] Есть второй реальный use case
- [ ] Semantics действительно совпадают
- [ ] API abstraction проще двух локальных реализаций
- [ ] Module-specific terms не протекают в platform
- [ ] Тесты можно написать независимо от конкретного модуля
- [ ] Abstraction не блокирует различия будущих modules

---

# Заключение

Текущий проект уже прошёл самый хаотичный этап. Рабочий Cost Monitor существует, Excel parity защищена, feature boundaries заложены. Следующий скачок качества должен происходить не через очередное перемещение файлов, а через **осознанные архитектурные границы и инженерную дисциплину**.

Главная траектория:

```text
Рабочий MVP
   ↓
Типизированный и проверяемый module foundation
   ↓
Контролируемая runtime configuration
   ↓
Versioning + trace + admin lifecycle
   ↓
Canonical adapters + SQL-ready storage boundaries
   ↓
Второй реальный monitor
   ↓
Проверенная модульная аналитическая платформа
```

Смысл этой архитектуры - сохранить то, что было удобно в Excel: оперативность изменения предметных параметров. Но сделать это на другом уровне качества: с тестами, версиями, validation, audit, rollback и понятными границами ответственности.

Именно от этого документа следует строить последующие prompts для Codex: **не «переписать приложение правильно», а последовательно довести работающий модуль до платформенного уровня, не меняя его пользовательскую и расчётную сущность.**
