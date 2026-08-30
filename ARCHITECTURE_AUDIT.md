# Architecture Audit

Дата аудита: 2026-08-30  
Репозиторий: `Web view monitors`  
Текущая ветка: `codex/architecture-foundation`
Проверенный commit: `603637a feat: complete cost monitor architecture foundation`

Implementation update (2026-08-30): на ветке
`codex/architecture-foundation` выполнен первый этап миграции. Добавлен
пяти-плечевой Excel golden master и API characterization tests; backend и
frontend сгруппированы под Cost Monitor feature. Findings F-06, F-07 и F-10
частично закрыты, остальные findings остаются актуальными.

Область аудита: фактическая архитектура frontend, backend, хранения данных,
импорта источников, расчётного ядра и тестов. Production-код, API, формулы, UI и
поведение приложения в рамках аудита не изменялись.

## 1. Current architecture

Проект представляет собой небольшой модульный монолит:

- FastAPI одновременно служит composition root, API-контроллером для всех
  функций и production-хостом собранного React-приложения.
- React/TypeScript — single-page application без router/state-библиотек. Четыре
  экрана переключаются локальным состоянием в `App.tsx`.
- Всё изменяемое состояние хранится одним JSON-документом
  `backend/data/store.json`: конфигурация источников, импортированные данные,
  ручные тарифы, черновики и аудит.
- Excel-файлы выбираются из настраиваемых каталогов и синхронно разбираются
  `openpyxl`; курс USD запрашивается у ЦБ РФ во время импорта реестра.
- Расчёт вызывается как функция `calculate(state, request)` и не обращается к
  HTTP, filesystem или хранилищу напрямую.
- JSON- и XLSX-экспорты строятся из одного результата расчёта.

Фактические крупные блоки:

| Блок | Реализация | Текущая ответственность |
|---|---|---|
| Entry point | `backend/app/main.py` | FastAPI, CORS, feature router composition, static frontend |
| Cost Monitor API | `backend/app/modules/cost_monitor/api.py` | Cookie, все текущие feature endpoints и JSON store composition |
| Request DTO | `backend/app/modules/cost_monitor/schemas.py` | Pydantic-модели входных данных |
| Runtime config | `backend/app/core/config.py` | Пути из environment и локальные defaults |
| State/persistence | `backend/app/modules/cost_monitor/store.py` | Начальное cost-monitor state, миграция JSON, read/mutate, audit/revision |
| Calculation | `backend/app/modules/cost_monitor/calculation.py` | Тарифный индекс, расчёт плеча, компонентов и итогов |
| Source import | `backend/app/modules/cost_monitor/sources.py`, `source_files.py`, `parsers/` | Оркестрация импорта, файловый ввод и когерентные Excel-парсеры |
| Export | `backend/app/modules/cost_monitor/exports.py` | Общий export snapshot и сериализация JSON/XLSX |
| Frontend entry | `frontend/src/main.tsx` | React bootstrap |
| Frontend application | `frontend/src/features/cost-monitor/CostMonitorApp.tsx`, `pages/` | Shell/API orchestration и отдельные feature-страницы |
| Frontend API/types | `frontend/src/features/cost-monitor/api.ts`, `types.ts` | HTTP client и вручную продублированные TypeScript DTO |

## 2. Dependency flow

```text
Browser / React App.tsx
    -> frontend/src/features/cost-monitor/api.ts
    -> HTTP / JSON / cookie
    -> backend/app/main.py (composition root)
    -> backend/app/modules/cost_monitor/api.py (FastAPI handlers)
        -> backend/app/modules/cost_monitor/schemas.py (request validation)
        -> backend/app/modules/cost_monitor/store.py (whole-state read/mutate)
        -> backend/app/modules/cost_monitor/calculation.py
            -> backend/app/modules/cost_monitor/catalog.py
        -> backend/app/modules/cost_monitor/exports.py
        -> backend/app/modules/cost_monitor/sources.py
            -> source_files.py / parsers/ -> filesystem / XLSX / ЦБ РФ
```

Зависимости ацикличны. Первоначальная нежелательная стрелка calculation ->
sources устранена через небольшой Cost Monitor catalog. Хранилище с его
бизнес-defaults перенесено внутрь Cost Monitor; в `core` осталась только общая
runtime-конфигурация.

## 3. Strong parts

- Расчёт отделён от FastAPI и filesystem. Его можно вызывать обычным unit-тестом
  с явными `state` и `request`; скрытого глобального состояния внутри формул нет.
- Внутри одного процесса JSON-запись атомарна (`tempfile` + `os.replace`) и
  защищена `RLock`; наружу возвращаются deep copies.
- Входные payload проходят Pydantic-валидацию, нормализацию кодов и числовые
  ограничения. Имя upload очищается через `Path(...).name`, а расширение
  ограничено `.xlsx`.
- Правила Excel, включая first-match, AER, техстоп и округление итогов,
  прокомментированы как намеренные invariants, а не случайная реализация.
- Импортированные и ручные тарифы неявно не подменяют друг друга: first-match
  остаётся совместимым с Excel, конфликт виден в UI.
- JSON и XLSX формируются из единого export snapshot, поэтому сами форматы не
  выполняют расчёт повторно и не расходятся по формулам.
- CORS ограничен двумя локальными origin, cookie `HttpOnly` и `SameSite=Lax`.
- Frontend собирается со strict TypeScript; централизованный API client одинаково
  обрабатывает основные HTTP-ошибки.
- Предупреждения расчётного ядра выводятся пользователю; активная data revision
  возвращается в API-результате, но отдельный UI-блок для неё удалён.
- Нет circular dependencies, избыточного DI, repository на каждую сущность,
  Redux/Zustand или других преждевременных enterprise-абстракций.
- Текущие `useState/useEffect` достаточны. Реальной необходимости во внешнем
  глобальном state manager сейчас нет.
- Reverse-engineering и baseline-документы существенно снижают риск случайного
  «улучшения» утверждённых Excel-правил.

## 4. Findings

### F-01

ID: F-01  
Severity: HIGH  
Area: Calculation reliability / data integrity  
Current behavior: При отсутствии маршрута, тарифа, коэффициента, scenario rate
или цены керосина отдельные компоненты заменяются нулём. Для части случаев есть
warning, но отсутствующие наземные услуги пропускаются без отдельного warning.
После failed refresh расчёт продолжает использовать старые данные; `refresh-all`
может успешно заменить только часть источников и создать смешанную ревизию. UI
всё равно показывает обычные итоговые карточки и разрешает экспорт.  
Why it is a problem: Финансово неполный результат выглядит как нормальный
результат. Warning не является машинно проверяемым признаком пригодности расчёта,
а mixed/stale state вообще не попадает в warnings расчёта.  
When it becomes a problem: При недоступности файла/ЦБ, ошибке парсинга,
неполном refresh-all, устаревшем источнике, новом аэропорте/типе ВС или ручном
вызове API с неполным input.  
Suggested direction: Ввести без изменения формул явную оценку readiness перед
расчётом и структурированный `calculation_status` (`valid`, `degraded`,
`blocked`) с причинами. Групповой refresh должен публиковать новый набор данных
как одно целое либо оставлять предыдущий набор активным. Политика того, какие
дефициты blocking, требует отдельного бизнес-решения.  
Must preserve: Числовое поведение и тексты текущих baseline-сценариев до
утверждения новой политики; Excel parity для полного валидного набора данных.

### F-02

ID: F-02  
Severity: HIGH  
Area: Reproducibility / exports / calculation history  
Current behavior: `data_revision` — счётчик изменяемого JSON state. Результат
содержит только revision и counts, а export snapshot не содержит даже этих
полей. Не сохраняются hashes/versions исходных файлов, parser/calculation
version, использованный курс и дата ЦБ, полная конфигурация данных или
неизменяемый input snapshot.  
Why it is a problem: Невозможно доказательно повторить или объяснить выгруженный
результат после очередного обновления данных. Одинаковый пользовательский input
может дать другой результат, а экспорт не сообщает, почему.  
When it becomes a problem: При аудите цифр, споре о тарифе, обновлении файлов,
изменении формул/парсера, появлении истории расчётов или нескольких пользователей.  
Suggested direction: Добавить immutable `DataSnapshot` с идентификатором,
source file metadata/hash, effective CBR rate/date, config values и версиями
parser/calculation rules; ссылаться на snapshot из результата и обоих экспортов.
Сохранение полного calculation record делать отдельно от черновика.  
Must preserve: Текущий request/response shape до версионированного расширения и
совпадение существующих экспортируемых чисел.

### F-03

ID: F-03  
Severity: HIGH  
Area: Persistence / concurrency / multi-user  
Current behavior: `JsonStore` читает и перезаписывает весь JSON (сейчас около
2 MB) при каждой mutation, включая debounce-autosave черновика. `RLock` защищает
только один Python-процесс. Два workers имеют независимые locks и могут прочитать
одну версию, после чего последний `os.replace` молча затрёт изменения первого.
Черновики не имеют срока жизни и увеличивают общий документ.  
Why it is a problem: Появляются lost updates, непредсказуемые revisions,
write amplification и глобальная сериализация несвязанных действий.  
When it becomes a problem: При нескольких uvicorn workers, параллельных
пользователях, сетевом deployment, росте тарифов/истории/черновиков.  
Suggested direction: Оставить JSON только как local adapter. Сначала отделить
операции application layer от whole-state dict, затем реализовать транзакционный
PostgreSQL adapter для реально сохраняемых агрегатов. Не вводить repository на
каждую сущность; достаточно узких портов для snapshots, drafts, source runs и
manual tariffs.  
Must preserve: Локальный single-process режим и существующую семантику revision
на время миграции.

### F-04

ID: F-04  
Severity: HIGH before any shared/network deployment; acceptable only for a
trusted local MVP  
Area: Security / authorization / filesystem  
Current behavior: Без authentication/authorization доступны изменение source
directory/mask, upload и overwrite `.xlsx`, refresh, добавление/удаление тарифов,
чтение raw preview, audit и server drafts. `/api/sources` раскрывает абсолютные
пути. Directory может указывать в любую доступную процессу область filesystem.  
Why it is a problem: Любой сетевой клиент сервиса получает права файлового
процесса и может менять расчётные данные.  
When it becomes a problem: Сразу при bind не только на loopback, публикации в
корпоративной сети, reverse proxy или совместном компьютере с недоверенными
пользователями.  
Suggested direction: До deployment ввести authentication и роли как минимум
`viewer`, `calculator`, `source_editor`; ограничить каталоги allowlisted roots,
не возвращать полные server paths обычному viewer, защищать mutation endpoints.
До этого явно запускать только на loopback.  
Must preserve: Текущий локальный workflow; отсутствие auth не требует срочного
рефакторинга для изолированного developer machine.

### F-05

ID: F-05  
Severity: MEDIUM  
Area: Security / uploads / source acquisition  
Current behavior: Upload проверяет только suffix `.xlsx`; лимитов размера,
ZIP-decompression budget, числа строк/ячеек и сигнатуры файла нет. Файл с тем же
именем заменяется без immutable copy. Маска и каталог полностью задаются через
API. Invalid workbook обнаруживается лишь на последующем refresh.  
Why it is a problem: Возможны disk/CPU/memory exhaustion, повреждение/подмена
последнего source file и потеря файла, по которому был получен результат.  
When it becomes a problem: При network access, больших/повреждённых книгах,
ошибочной загрузке поверх рабочего файла или автоматизации импорта.  
Suggested direction: Ограничить request и распакованный размер, количество
rows/cells/sheets, проверять ZIP/XLSX до публикации, хранить upload под
version/hash и атомарно активировать только после успешного parse. Валидировать
mask и resolved path внутри разрешённого root.  
Must preserve: Приём обычных `.xlsx`, выбор latest file и текущие parser rules.

### F-06

Status: ADDRESSED FOR CURRENT SCALE — feature router, catalog, store, файловый
ввод, orchestration и parser families имеют отдельные границы.  

ID: F-06  
Severity: MEDIUM  
Area: Backend modularity / dependency direction  
Current behavior: `main.py` является composition root; Cost Monitor API и store
находятся внутри feature. `sources.py` только применяет результат импорта,
`source_files.py` отвечает за файлы, а `parsers/` — за отдельные форматы Excel.
`calculate_leg` остаётся крупной, но когерентной реализацией формулы.  
Why it is a problem: Второй монитор потребует менять центральные файлы и
увеличит вероятность shotgun surgery. Название `core` обещает shared-код, но
фактически связывает будущие features с Cost Monitor.  
When it becomes a problem: При втором мониторе, новом parser/source type,
версионировании API и параллельной разработке.  
Suggested direction: Сгруппировать backend по feature: отдельный Cost Monitor
router/application/calculation/import/export; оставить в core только runtime
config, общие ошибки и composition. Generic file policy выделять в shared лишь
когда её действительно использует второй feature. Разбить `sources.py` по
приобретению/применению данных и когерентным parser families.  
Must preserve: Все URL/JSON contracts, physical order данных, формулы и порядок
вызовов расчёта.

### F-07

Status: MOSTLY ADDRESSED — feature entry/API/types и четыре страницы разделены;
application orchestration намеренно остаётся в `CostMonitorApp.tsx`.  

ID: F-07  
Severity: MEDIUM  
Area: Frontend modularity  
Current behavior: `CostMonitorApp.tsx` (около 326 строк) содержит shell,
navigation, API orchestration, autosave и Cost Monitor state. Страницы находятся
в `pages/`; глобальный store по-прежнему не требуется.  
Why it is a problem: Добавление второго монитора расширит центральный Page union,
state и content map; feature-specific UI трудно тестировать и переиспользовать
изолированно.  
When it becomes a problem: При втором мониторе, нескольких разработчиках,
route-based navigation или самостоятельных frontend tests.  
Suggested direction: Оставить `useState/useEffect`, но вынести AppShell/navigation,
Cost Monitor page/components и feature hooks (`useCalculationDraft`, source
operations) в отдельные модули. Shared UI/API base выделять только по факту
повторного использования. Redux/Zustand сейчас не нужны.  
Must preserve: Текущий UX, debounce/autosave semantics, API sequence и видимые
состояния загрузки/ошибок.

### F-08

ID: F-08  
Severity: MEDIUM  
Area: Frontend/backend responsibility  
Current behavior: Backend уже возвращает `details` для АНО, бортпитания и НДС,
но `ComponentBreakdown` повторно выводит части из totals с константами `1666.6`,
`6 × 1500`, `500` и `0.1`.  
Why it is a problem: Presentation может разойтись с backend-формулой и показать
неверную детализацию при сохранении правильного total. Это дублирование
calculation knowledge во frontend.  
When it becomes a problem: При любом согласованном изменении формулы, новой
версии расчёта или отличающемся втором мониторе.  
Suggested direction: После фиксации контрактов рендерить backend `details` как
источник истины; во frontend оставить только labels/formatting.  
Must preserve: Текущие суммы и визуальное содержание детализации.

### F-09

ID: F-09  
Severity: MEDIUM  
Area: Frontend <-> backend contract  
Current behavior: Pydantic описывает request DTO, но почти все responses
объявлены как `dict[str, Any]`/`list[dict[str, Any]]`; OpenAPI показывает
`additionalProperties: true`. TypeScript interfaces поддерживаются вручную.
Нет runtime-validation ответа. `legs` допускает пустой список и duplicate ids;
`techstop_leg_id` не проверяется против ids legs.  
Why it is a problem: Backend и frontend могут разойтись без ошибки компиляции на
сервере; duplicate ids делают techstop и экспорт неоднозначными; второй monitor
увеличит число неявных contracts.  
When it becomes a problem: При перестройке модулей, расширении результата,
versioned API, внешнем клиенте или duplicate/invalid API input.  
Suggested direction: Добавить явные response DTO и contract tests, затем
генерировать или проверять frontend types по OpenAPI. Существующие Cost Monitor
routes оставить стабильными; новые monitor API группировать собственным prefix.
Входные cross-field invariants валидировать на границе request DTO.  
Must preserve: Нынешние имена полей и observable status codes до отдельной
версии API.

### F-10

Status: PARTIALLY ADDRESSED — добавлен Excel-owned пяти-плечевой golden master,
API/export shape, parser characterization и reliability tests; расширенная
scenario matrix ещё нужна.

ID: F-10  
Severity: HIGH as a refactoring gate; MEDIUM for the unchanged local MVP  
Area: Tests / Excel parity  
Current behavior: 26 backend tests проверяют synthetic cases, JSON/XLSX
packaging, preview, persistence migration, partial refresh, parser
characterization и Excel-owned пяти-плечевой golden master. Golden fixture
сверяет все компоненты каждого плеча и итоговые М1/М2/М3 с утвержденными
кэшированными значениями Excel. Нет проверки исходной книги через Excel runtime,
concurrency, invalid/large upload или frontend tests.
Why it is a problem: Текущие тесты не доказывают calculation parity с эталонным
Excel и недостаточны для безопасного перемещения/разбиения расчётного кода.  
When it becomes a problem: При первом существенном архитектурном refactoring,
изменении parser, обновлении библиотек или переносе persistence.  
Suggested direction: До перестройки calculation/import создать versioned,
обезличенные golden fixtures: нормализованный input snapshot + expected result
из Excel по каждому плечу/компоненту и итогам. Сравнивать Decimal/float по явно
зафиксированным правилам округления. Отдельно зафиксировать parser golden outputs
и порядок duplicate keys.  
Must preserve: Исходный Excel остаётся эталоном; expected values не следует
«обновлять» автоматически из Python при падении теста.

### F-11

ID: F-11  
Severity: MEDIUM  
Area: Error handling / observability  
Current behavior: Ошибки ЦБ РФ ловятся `except Exception` и превращаются в
fallback 95 RUB/USD. Refresh endpoints возвращают объект source со статусом
`error` и HTTP 200. Raw preview отображает любое исключение как 404 и передаёт
`str(error)` клиенту. Audit хранит только последние 100 событий в том же JSON;
структурного logging/correlation id нет.  
Why it is a problem: Автоматический клиент может принять неуспешный refresh за
успех, причины ошибок смешиваются, filesystem details могут раскрыться, а
финансово важный fallback не связан с конкретным calculation result.  
When it becomes a problem: При автоматизации, поддержке production, incident
analysis и сетевом доступе.  
Suggested direction: Ввести общую типизированную модель ошибок и structured
logging; различать not-found/invalid-file/internal errors; сделать fallback
явным quality flag источника и snapshot. Смена status codes — только через
согласованное версионирование контракта.  
Must preserve: Пользователь должен получать понятную причину, а старые данные не
должны уничтожаться при неуспешном parse.

### F-12

ID: F-12  
Severity: LOW  
Area: Build/configuration portability  
Current behavior: Backend dependencies заданы диапазонами без lock-файла и без
зафиксированной версии Python; default source path содержит конкретный
`C:/Users/soale/Downloads`. Frontend имеет lock-файл.
Why it is a problem: Новое окружение может получить иной dependency graph или
локальный path.
When it becomes a problem: При CI, onboarding, deployment или обновлении
окружения.  
Suggested direction: Зафиксировать поддерживаемую Python version и
воспроизводимый backend lock после выбора packaging tool; оставить source path
только environment/config default.
Must preserve: Возможность переопределения путей environment variables.

Не обнаружены: circular dependencies, скрытый global state внутри calculator,
прямой filesystem access из calculation, небезопасный filename traversal через
имя upload, преждевременный global frontend store или чрезмерный слой
interfaces/factories.

## 5. Calculation reliability

Главный вывод: Calculation Engine может вернуть внешне правдоподобный итог,
когда часть входных данных заменена нулём, default или fallback. Warnings снижают
риск для внимательного пользователя, но не делают результат воспроизводимым и
не запрещают экспорт.

| Ситуация | Текущее поведение | Риск |
|---|---|---|
| Missing route | `flight_time`, distance, fuel tons и margins становятся 0; есть warning, но питание/часть ground могут остаться ненулевыми | Итог выглядит частично рассчитанным |
| Missing CRT fuel tariff | Каждая из двух ставок даёт warning и 0 | Degraded total всё равно возвращается |
| Missing ground tariff | `add_service` молча возвращает 0 | Пользователь не знает, какая услуга исключена |
| Missing АНО tariff | АНО 0 и warning | Итог возвращается |
| Missing aircraft coefficient | Множитель 0 и warning; unit-based ground остаётся | Частично нулевой расчёт |
| Missing scenario/aircraft rate | Все три margins 0 и warning | M1/M2/M3 могут выглядеть почти одинаково |
| Missing АК price | Fuel 0 и warning | Итог возвращается |
| Failed refresh | Старые parsed data сохраняются, source получает error | Calculator не маркирует result как stale/error |
| Partial refresh-all | Успешные sources заменены, failed sources остаются старыми; revision повышается один раз | Одна revision скрывает смесь поколений |
| Stale source | Возраст данных отображается только на source page; TTL/readiness policy нет | Старые данные считаются активными |
| Duplicate tariff | Используется первая физическая строка по Excel baseline | Намеренно, но origin/order должны быть в snapshot/golden tests |
| Invalid workbook | Upload может заменить файл; refresh падает, старые parsed data остаются | Файл и активные данные расходятся |
| ЦБ РФ unavailable | Fuel import использует 95 RUB/USD и note у source | Calculation/export не содержит quality flag и курс |
| Empty/duplicate leg ids через API | Пустой расчёт возвращает нулевые totals; duplicate id неоднозначен для techstop/export | Неявный request invariant |

Для архитектурной переработки нельзя сначала «почистить» эти формулы. Сначала
нужны golden-master tests и явное описание validity metadata; новая политика
blocking/degraded результатов должна согласовываться отдельно от refactoring.

## 6. Security

Текущий уровень приемлем только при запуске доверенным пользователем на loopback.

- HIGH deployment gate: отсутствие authentication/authorization на всех read и
  mutation endpoints, включая source paths, upload, refresh и тарифы.
- HIGH deployment gate: source directory — произвольный server path; raw preview
  и upload работают с правами процесса.
- MEDIUM: нет upload/request/decompression limits и content validation beyond
  `.xlsx`; возможен resource-exhaustion.
- MEDIUM: overwrite файла с тем же именем без версии/backup; нет quarantine до
  успешного parse.
- MEDIUM: absolute paths и `str(exception)` возвращаются клиенту.
- MEDIUM при появлении auth: нет явной CSRF strategy. `SameSite=Lax` и узкий CORS
  помогают локально, но не заменяют design для будущей session auth.
- LOW локально: draft cookie `Secure=False`; перед HTTPS deployment должен стать
  Secure с согласованными cookie settings.
- LOW локально: drafts и calculation inputs хранятся незашифрованными в JSON и
  localStorage; retention/ownership отсутствуют.

Положительные меры: origin не wildcard, upload filename очищается до basename,
разрешено только `.xlsx`, Pydantic ограничивает основные строки/числа, stack
trace напрямую FastAPI не возвращает при стандартной конфигурации.

## 7. Scalability

| Направление | Текущее состояние | Требуемая граница |
|---|---|---|
| Multi-user | Один JSON, анонимные cookie drafts, общие source settings | Auth ownership/roles, транзакционное persistence, draft retention |
| Database | Calculator получает plain state и не знает JSON — это хороший seam; API/services знают whole dict | Application operations + PostgreSQL adapter, без repository на каждое поле |
| Second monitor | Backend/Frontend центральные файлы Cost-specific; core state загрязнён Cost Monitor | Feature modules с собственными routes/schemas/UI/calculator/import rules |
| Multiple workers | Межпроцессного lock/transaction нет | External transactional store; parsing job coordination |
| Source import | Синхронен внутри request; refresh-all последователен и частичен | Versioned staging/activation; background job только когда длительность этого потребует |
| Calculation history | Есть только draft и mutable data revision | Immutable calculation record -> immutable data snapshot |
| Data volume | Каждый request читает/копирует весь 2 MB state; tariffs API отдаёт весь filtered list до client slice | Query/pagination и indexed DB после реального роста |

Redis, broker, microservices и background workers сейчас добавлять не нужно.
Первое обязательное инфраструктурное изменение для shared deployment —
транзакционное внешнее persistence; очередь оправдана только измеренной
длительностью/конкуренцией source import.

## 8. Testability

Сильная сторона — pure-ish calculator и небольшое число зависимостей. Текущие
26 tests быстры и покрывают:

- first-match tariff и сумму нескольких legs;
- catering toggle, АК fuel, techstop, missing route/fuel warnings;
- data revision propagation и произвольное число legs;
- общий JSON/XLSX export snapshot;
- workbook preview, manual conflict и source error marking;
- JSON persistence/recreation и простую migration.
- пяти-плечевой Excel golden master, API operation set, export shape, partial
  refresh и fallback ЦБ.

Критические пробелы:

- golden master использует кэшированные значения утвержденного Excel, а не
  запуск Excel runtime;
- нет versioned fixtures из реальных SRV/registry/monitor workbook и полной
  проверки physical order/duplicates;
- нет CBR rate/date fixture или test fallback metadata;
- нет stale/invalid workbook/atomic activation tests;
- нет API response/status-code contract tests;
- нет multi-process/concurrency/lost-update tests;
- нет frontend tests на autosave race, warnings и backend-driven details.

Рекомендуемый Excel parity harness:

```text
versioned source fixture(s)
    -> normalized immutable data snapshot
known calculation request
    -> Excel-owned expected JSON (inputs, per-leg components/details, totals)
Python calculator
    -> structural comparison + explicit numeric rounding/tolerance
```

Expected JSON должен быть получен/утверждён из Excel и храниться отдельно от
кода, который его проверяет. Нельзя генерировать expected Python-калькулятором.
Минимальная матрица: текущие пять плеч, normal/МВЛ, ЦРТ/АК, techstop,
catering on/off, missing reference, duplicate first-match и >5 legs.

## 9. Recommended target architecture

Рекомендуется сохранить модульный монолит и один deployable backend/frontend.
Целевая структура группирует изменения по feature, а shared-код выделяет только
при доказанном повторном использовании.

```text
backend/
  app/
    main.py                         # composition root, middleware, router mount, static UI
    core/
      config.py                     # runtime configuration only
      errors.py                     # typed application/API errors
      logging.py                    # structured logging setup
    infrastructure/
      json_state.py                 # local-only adapter during migration
      database.py                   # shared DB/session setup when PostgreSQL is introduced
      file_policy.py                # allowed roots, upload limits, atomic version storage
    modules/
      cost_monitor/
        api.py                      # current Cost Monitor routes, stable URLs
        schemas.py                  # explicit request and response DTO
        application.py              # orchestration/readiness/snapshot selection
        calculation.py              # formulas; no HTTP/filesystem/database
        exports.py                  # packages completed calculation record
        sources.py                  # Cost Monitor import orchestration
        parsers/
          tariffs.py                # SRV rules
          fuel.py                   # registry normalization; injected rate input
          workbook.py               # routes/config/manual legacy import
        storage.py                  # narrow feature persistence port when needed
      future_monitor/
        ...                         # own API, schemas, application and domain rules
  tests/
    parity/                         # Excel-owned golden fixtures/results
    cost_monitor/
    contracts/

frontend/
  src/
    main.tsx
    app/
      App.tsx                       # bootstrap only
      AppShell.tsx                  # navigation/layout
    shared/
      api/client.ts                 # generic HTTP/error transport
      ui/                           # only genuinely reused primitives
      formatting.ts
    features/
      cost-monitor/
        api.ts
        types.ts
        hooks/useCalculationDraft.ts
        pages/CalculatorPage.tsx
        components/
      source-management/
        api.ts
        pages/SourcesPage.tsx
        pages/SettingsPage.tsx
      tariffs/
        api.ts
        pages/TariffsPage.tsx
      future-monitor/
        ...
```

`source-management` и `tariffs` не следует объявлять universally shared domain:
они могут остаться модулями Cost Monitor, пока второй монитор не подтвердит
реальное переиспользование. Нужен не Clean Architecture целиком, а три ясные
границы: transport -> application -> pure calculation, плюс infrastructure
adapters, вызываемые application layer.

Стабильными следует оставить:

- пользовательские calculation inputs и текущие формулы;
- `/api/calculations`, drafts, source/tariff operations и export formats до
  контролируемой версии API;
- first physical tariff match и порядок imported before manual;
- единый backend source of truth для результатов/details;
- возможность локального запуска без PostgreSQL на переходных этапах.

## 10. Migration strategy

### Stage 1 — Freeze the behavioral baseline (completed for the primary scenario)

- Создать architecture branch `codex/architecture-foundation`.
- Добавить обезличенные versioned fixtures и Excel-owned golden expected JSON.
- Зафиксировать current API response shapes и export content contract tests.
- Покрыть partial refresh, fallback и duplicate/input invariants как текущее
  поведение, не исправляя формулы.
- Exit criterion: нынешние 26 tests, parity suite и frontend build проходят.

### Stage 2 — Split frontend by feature (feature boundary established; component split pending)

- Переместить существующие компоненты без визуальных изменений.
- Вынести API orchestration/autosave в feature hooks.
- Перевести breakdown на уже возвращаемые backend details после contract test.
- Не добавлять global state manager/router, если их ещё не требует второй screen
  flow.
- Exit criterion: DOM/UX/API calls observable-equivalent, build/tests проходят.

### Stage 3 — Establish backend feature boundaries (initial module/router split completed)

- Вынести FastAPI routers и Cost Monitor schemas/application/calculation/export.
- Устранить dependency calculator -> sources через Cost Monitor-owned normalized
  input/catalog helpers.
- Разделить source acquisition и parsers; сохранить compatibility imports при
  необходимости.
- Exit criterion: URL/status/JSON/golden outputs неизменны.

### Stage 4 — Add reproducible data snapshots and validity metadata

- Staging -> validate -> atomic activation для source set.
- Immutable source/data snapshot metadata, CBR rate/date и rule versions.
- Расширить result/export snapshot id и structured quality status.
- Любое blocking/degraded правило согласовать как API/business behavior change.
- Exit criterion: каждый экспорт однозначно связан с воспроизводимым snapshot.

### Stage 5 — Replace local persistence for shared use

- Реализовать PostgreSQL adapter и миграцию active data/manual tariffs/drafts.
- Добавить ownership/retention, auth roles и path/upload policy.
- JSON adapter оставить только для local development до окончания перехода.
- Exit criterion: concurrency/integration tests проходят с несколькими workers.

### Stage 6 — Add the second monitor through the new seams

- Собственные API prefix, schemas, calculator, source adapters и frontend feature.
- Переиспользовать только доказанно общие config/auth/files/UI pieces.
- Exit criterion: добавление feature не требует изменения Cost Monitor formulas.

После каждого stage приложение остаётся рабочим; big-bang rewrite не требуется.

## 11. Things NOT worth changing

- FastAPI + React/TypeScript и модульный монолит подходят текущему размеру.
- Чистый функциональный entry `calculate(state, request)` — удачная основа; не
  нужен DI container или class hierarchy ради формальности.
- `useState/useEffect` достаточно; Redux/Zustand сейчас увеличат сложность.
- JSON store допустим для одного доверенного local process до начала shared use.
- Atomic temp-file write и deep-copy semantics не требуют косметической замены.
- First-match tariff, AER rules, hardcoded formula constants,
  rounding и fallback сейчас нельзя «исправлять» как часть архитектуры.
- `openpyxl`, synchronous request flow, отсутствие Redis/broker/Docker допустимы,
  пока измерения не покажут operational need.
- Отдельный microservice на monitor/source/export не нужен.
- CSS/UI/UX не входят в архитектурную миграцию.

## 12. Proposed next task

Следующий безопасный scope после выполненного структурного разделения:

> Зафиксировать frontend autosave/API sequence и пограничное округление
> детализации тестами. Только затем заменить повторные UI-формулы данными
> backend `details` и при необходимости вынести orchestration в feature hooks.

Immutable data snapshots/readiness metadata остаются следующим продуктовым
этапом: blocking/degraded policy требует отдельного решения владельца продукта.
