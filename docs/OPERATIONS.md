# Эксплуатация

## Требования и окружение

CI проверяет Python 3.12, Node 22 и pnpm 11.19.0. Для production необходимо
явно задать `APP_ENV=production`, `MONITOR_DATA_DIRECTORY`,
`MONITOR_SOURCE_DIRECTORY`, `HOST`, `PORT` и `LOG_LEVEL`. Директории данных и
источников должны существовать, быть абсолютными и доступны для чтения/записи.
В `.env.example` перечислены несекретные настройки.

Значения по умолчанию для разработки находятся в репозитории. Production
никогда не использует developer-директорию Downloads как запасной путь.

## Сборка и запуск

```powershell
pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend build
Push-Location backend
..\.venv\Scripts\python -m app
Pop-Location
```

В production `/` и `/admin` обслуживаются из `frontend/dist`; не используйте
`--reload`, `pnpm dev` или более одного worker, пока активен JsonStore.

`/api/health` подтверждает, что процесс отвечает. Для `/api/ready` дополнительно
нужны читаемый store, корректные активные Configuration и Reference Data, а
также инициализированные данные SRV/Fuel Registry. До этого состояния endpoint
возвращает 503.

## Резервное копирование, восстановление и наблюдаемость

Остановите единственный процесс приложения перед резервным копированием или
восстановлением. Скопируйте всю настроенную директорию данных (включая
`store.json`), требуемые активные файлы источников и deployment-настройки,
хранящиеся вне Git. Восстановите тот же согласованный набор, запустите один
worker и проверьте `/api/ready`; так сохраняются версии, audit history и
ревизия live-данных.

Request logs используют текстовые поля `key=value`: timestamp, level, endpoint,
ошибку, версию Configuration, версию Reference Data и revision данных. Тела
запросов, cookies и credentials не логируются.

## Безопасность

В production применяется same-origin, а draft cookies имеют флаги Secure,
HttpOnly и SameSite Lax; HTTPS завершается перед приложением. Это не является
авторизацией. Corporate authentication/RBAC отсутствует и является P0-блокером
для сетевого развёртывания, особенно для mutation API `/admin`.
