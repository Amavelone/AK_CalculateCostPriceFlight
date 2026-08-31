# Монитор расчета себестоимости

Рабочее приложение для расчета себестоимости рейсов, управления файлами-источниками и единым справочником подключенных услуг.

Текущий этап — первая реализованная версия по материалам в `docs/`. Расчетное ядро и загрузчики источников отделены от интерфейса, чтобы новые мониторы можно было добавлять самостоятельными модулями.

## Запуск для разработки

1. Создайте виртуальное окружение и установите backend-зависимости:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\python -m pip install -r backend\requirements.txt
   ```

2. Установите frontend-зависимости:

   ```powershell
   cd frontend
   pnpm install
   ```

3. При необходимости укажите директорию, в которой находятся Excel-файлы:

   ```powershell
   $env:MONITOR_SOURCE_DIRECTORY = 'C:\\путь\\к\\выгрузкам'
   ```

4. В разных терминалах запустите API и интерфейс:

   ```powershell
   .\.venv\Scripts\python -m uvicorn app.main:app --app-dir backend --reload --port 8000
   cd frontend; pnpm dev
   ```

Откройте `http://localhost:5173`. На странице «Источники» можно проверить пути и запустить парсинг актуальных файлов.
В просмотре исходного файла можно выбрать любой лист книги; для реестра 1С
интерфейс автоматически находит рабочую строку заголовков после служебных строк.

После `pnpm build` FastAPI также отдает собранный интерфейс по адресу
`http://localhost:8000`, поэтому для демонстрационного запуска достаточно API.

## Production runtime

Production запускается только с явными значениями `APP_ENV=production`,
`MONITOR_DATA_DIRECTORY`, `MONITOR_SOURCE_DIRECTORY`, `HOST`, `PORT` и
`LOG_LEVEL`. Оба каталога должны уже существовать, быть абсолютными и доступны
для чтения/записи; fallback на developer Downloads отсутствует. Нешаблонные
значения не хранятся в Git — используйте `.env.example` как перечень settings.

```powershell
$env:APP_ENV = 'production'
$env:MONITOR_DATA_DIRECTORY = 'C:\\cost-monitor\\data'
$env:MONITOR_SOURCE_DIRECTORY = 'C:\\cost-monitor\\sources'
$env:HOST = '127.0.0.1'
$env:PORT = '8000'
$env:LOG_LEVEL = 'INFO'
pnpm --dir frontend build
Push-Location backend
..\.venv\Scripts\python -m app
Pop-Location
```

Не используйте `--reload`, `pnpm dev` или несколько workers: до миграции на SQL
Server JsonStore поддерживается только как **one server / one process / one
worker**. HTTPS завершается перед приложением; production использует same-origin
без CORS, а cookie draft имеет `Secure`, `HttpOnly` и `SameSite=Lax`.

`GET /api/health` проверяет только доступность процесса. `GET /api/ready`
возвращает 200 лишь при читаемом store, валидных active Configuration и
Reference Data, а также активированных SRV и Fuel Registry с непустыми
canonical данными; иначе это 503 с безопасным списком checks. Legacy Workbook
не входит в readiness.

Логи запроса имеют текстовый формат `key=value` и содержат timestamp, level,
endpoint, error, config/reference versions и data revision; содержимое запросов,
cookie и credentials не логируются.

### Backup and recovery

1. Остановите единственный процесс приложения.
2. Копируйте как единый backup весь `MONITOR_DATA_DIRECTORY` (включая
   `store.json`), необходимые активные файлы из `MONITOR_SOURCE_DIRECTORY` и
   deployment settings вне Git.
3. Для восстановления замените эти каталоги согласованной копией, сохраните
   ownership/permissions, запустите один process/worker и проверьте
   `/api/ready`.

Так сохраняются версии Configuration/Reference Data, active live data и audit
history; не редактируйте `store.json` вручную во время работы процесса.

## Администрирование configuration

Пользовательский Cost Monitor остаётся на `/`. Отдельный административный
контур открывается на `http://localhost:5173/admin` в Vite или
`http://localhost:8000/admin` после `pnpm build`.

В `/admin` можно создать draft, изменить typed parameters и разрешённые части
ANO/Catering/VAT, выполнить validation, preview/compare на контрольном input,
activate новую версию или rollback. Active configuration нельзя редактировать
напрямую. Route разделяет интерфейсы, но пока не является security boundary:
authentication/RBAC не реализованы.

## Проверка

```powershell
$env:PYTHONPATH = (Resolve-Path .\backend).Path
.\.venv\Scripts\python -m unittest discover -s .\backend\tests -v
.\.venv\Scripts\ruff check backend
Push-Location frontend
pnpm exec tsc -b
pnpm exec vite build
Pop-Location
```

Контрольный сценарий из приложенной книги — пять плеч на листе `РАСЧЕТ` с
техстопом `BAX-HMA`, источником ГСМ `ЦРТ` и отключенной пассажирской доплатой
за питание — воспроизводит итоговые М1/М2/М3 текущей книги до копейки.

## Хранение данных

Для локальной разработки используется файловое хранилище `backend/data/store.json`, которое автоматически создается и не попадает в Git. Оно сохраняет настройки, версии источников, ручные услуги и черновики расчетов между перезапусками. Слой хранения изолирован; переход к SQL Server отложен до стабилизации configuration/versioning contracts и не должен менять расчетное ядро.

После успешного атомарного обновления **всех** источников или изменения ручной услуги увеличивается
номер активной версии данных. Он возвращается вместе с результатом расчета и
помогает связать итоговую себестоимость с тем набором данных, на котором она
была получена.

Calculation configuration versioned отдельно от dataset: она содержит safe
typed operations и explicit overrides для aircraft multipliers/scenario rates.
ANO, Catering и VAT можно менять только внутри зарегистрированных Cost Monitor
capabilities; arbitrary Python, filesystem, HTTP и database access из
configuration невозможны.

Загружаемый XLSX ограничен 25 МБ и проверяется до публикации. Просмотр исходной
книги показывает последний успешно активированный файл, а не незавершённый upload.

## Важные ограничения

- v1 поддерживает ВВЛ; Legacy Monitor Workbook остаётся только DEV compatibility
  tooling и не участвует в production runtime.
- `/admin` и same-origin route separation не являются security boundary.
  Корпоративные authentication/RBAC пока не определены: это P0 blocker для
  network deployment, поэтому не публикуйте mutation API во внешней сети без
  утверждённого механизма доступа.
- SQL Server, bulk CSV/XLSX import Reference Data и MВЛ остаются deferred.
#
