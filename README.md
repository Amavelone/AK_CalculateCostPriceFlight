# Cost Monitor v1.0.2

Cost Monitor рассчитывает себестоимость плеч рейса для операционных
пользователей. Сервис объединяет утверждённую Configuration расчёта,
версионируемые справочные данные и актуальные источники SRV/Fuel Registry,
после чего возвращает прослеживаемые результаты M1/M2/M3 и выгрузки JSON/XLSX.

## Поддерживаемая область v1

- Плечи ВВЛ в любом количестве, одна необязательная техническая посадка,
  источники ГСМ `ЦРТ`/`АК` и необязательная доплата за пассажирское питание.
- Версионируемые Configuration и Reference Data с жизненным циклом
  draft/validate/preview/compare/activate/rollback в `/admin`.
- Production-источники SRV и Fuel Registry с атомарной операцией `refresh-all`.
- Справочник маршрутов, Airport Other Costs и ручные тарифы; выгрузки JSON/XLSX.

МВЛ не входит в область v1. Legacy Monitor Workbook используется только как DEV
инструмент совместимости и никогда не является production-источником runtime.

## Архитектура и документы

```text
Calculation Configuration + Reference Data + Live Sources
                         -> Effective Context -> Calculation
```

- [Архитектура](docs/ARCHITECTURE.md)
- [Базовые правила расчёта](docs/CALCULATION.md)
- [Configuration и Reference Data](docs/CONFIGURATION.md)
- [Эксплуатация и восстановление](docs/OPERATIONS.md)

## Требования и окружение

Используйте Python 3.12, Node 22 и pnpm 11.19.0. В `.env.example` перечислены
все несекретные environment variables. Для production необходимы явно заданные
`APP_ENV=production`, директории данных и источников, host, port и log level;
сервис не использует developer-пути как запасной вариант.

## Запуск для разработки

```powershell
py -m venv .venv
.\.venv\Scripts\python -m pip install -r backend\requirements.txt
Push-Location frontend
pnpm install --frozen-lockfile
pnpm dev
Pop-Location
.\.venv\Scripts\python -m uvicorn app.main:app --app-dir backend --reload --port 8000
```

Откройте `http://localhost:5173`. Указывайте `MONITOR_SOURCE_DIRECTORY` только
когда доступны локальные исходные workbook-файлы.

## Тестирование и сборка

```powershell
$env:PYTHONPATH = (Resolve-Path .\backend).Path
.\.venv\Scripts\python -m unittest discover -s .\backend\tests -v
.\.venv\Scripts\ruff check backend
Push-Location frontend
pnpm install --frozen-lockfile
pnpm exec tsc -b
pnpm exec vite build
Pop-Location
```

GitHub Actions выполняет эти release-проверки при push и pull request.

## Production-запуск и маршруты

Соберите frontend, задайте все production-переменные из `.env.example`, затем
запустите:

```powershell
Push-Location backend
..\.venv\Scripts\python -m app
Pop-Location
```

FastAPI обслуживает `/` и `/admin` из `frontend/dist`. Пока адаптером хранения
является JsonStore, не используйте reload и запускайте ровно один worker. Доступны
маршруты `/`, `/admin`, `/api/health` и `/api/ready`.

`/api/ready` возвращает 503, пока не инициализированы store, активные
Configuration и Reference Data, а также оба production-источника. О резервном
копировании, логировании и операциях с источниками см. [эксплуатационную
документацию](docs/OPERATIONS.md).

## Администрирование и ограничения

`/admin` управляет business-oriented draft-версиями Configuration и Reference
Data. Default Configuration v1 — видимый immutable baseline release: из него
или из текущей Active можно создать draft, но его нельзя изменить, удалить или
перезаписать. Basic mode показывает предметные параметры топлива, НО, АНО,
питания, НДС и M1/M2/M3; Advanced mode раскрывает только разрешённые модулем
operations/lookup details. Versions можно сравнить с Default, preview остаётся
неактивирующим, а Configuration можно выгрузить в JSON. Настройка источников и
ручные тарифы остаются в основном приложении.

JsonStore ограничен одним сервером, одним процессом и одним worker до перехода
на SQL Server. Corporate authentication/RBAC отсутствует: это P0-блокер для
сетевого развёртывания, а разделение маршрутов `/admin` не является границей
авторизации.
