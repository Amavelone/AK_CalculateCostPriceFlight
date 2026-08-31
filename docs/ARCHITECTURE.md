# Архитектура

## Область применения

Cost Monitor v1 рассчитывает себестоимость плеч рейсов ВВЛ. Только backend
владеет правилами расчёта; React отображает типизированные результаты API и не
воспроизводит формулы. Версия релиза приложения задаётся файлом `VERSION` в
корне репозитория.

```text
Calculation Configuration + Reference Data + Live Sources
                         -> Effective Context -> Calculation -> JSON/XLSX
```

## Границы runtime

- **Configuration** — неизменяемая версионируемая операционная логика и
  утверждённые значения для типов ВС и сценариев.
- **Reference Data** — неизменяемые версионируемые Routes и Airport Other Costs.
- **Live Sources** — только SRV и Fuel Registry. Их атомарное обновление меняет
  канонические тарифы/цены топлива и `data_revision`.
- Расчёт содержит `config_version`, `reference_version` и `data_revision`;
  активация Configuration или Reference Data не меняет live-данные.

`refresh-all` подготавливает оба live-источника и при ошибке не активирует ни
один. Импортированные строки тарифов предшествуют ручным, сохраняя значимый для
parity первый физический match дублирующихся ключей. Округление расчёта и
структура M1/M2/M3 покрыты Excel golden-parity suite.

## Хранение и совместимость

JsonStore — локальный атомарный файловый адаптер. Пока он не заменён, в
production допустимы строго один сервер, один процесс и один worker. Контракт
хранения изолирует модуль расчёта от будущего адаптера SQL.

Парсер Legacy Monitor Workbook и его адаптер используются только для DEV
совместимости. Они не регистрируются при запуске, в production UI источников,
обновлении источников, readiness или жизненном цикле расчёта.

## Отложенные границы

МВЛ, SQL Server, corporate authentication/RBAC и массовый импорт Reference Data
не входят в v1. Перед сетевым доступом к mutation endpoint'ам администрирования
необходимы authentication/RBAC.
