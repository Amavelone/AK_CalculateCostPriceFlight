# Configuration и Reference Data

## Configuration

Схема Configuration `2.0` владеет типизированными параметрами расчёта,
утверждёнными множителями типов ВС и ставками сценариев M1/M2/M3. Разрешены
только зарегистрированные variables, functions и operations; произвольный код,
доступ к файловой системе, HTTP и базе данных запрещены.

Версии Configuration неизменяемы. **Default Configuration v1** — утверждённый
immutable baseline release. Его payload нельзя редактировать, удалять,
перезаписывать импортом или заменять активацией. Default может быть Active после
rollback, но rollback меняет только active pointer. Администратор создаёт draft
из Default либо Current Active, выполняет edit, validate, preview, compare,
activate или rollback. Безопасное удаление доступно только для draft; история
активированных версий сохраняется для provenance и rollback.

Basic mode предоставляет business representation: Топливо, Наземное
обслуживание, АНО, Бортовое питание, НДС и Лётный час/M1/M2/M3. Для каждого
параметра module-owned metadata содержит label, description, unit, bounds и
where-used. Basic update переводится только в зарегистрированные typed values и
не меняет operations. Advanced mode показывает bounded operations, bindings,
conditions и lookups только из capability whitelist модуля; arbitrary code не
поддерживается. Compare группирует изменения по business-разделам, сохраняя
technical path как вторичную деталь.

Configuration version или draft можно экспортировать в JSON с export/schema
version, identity/state, values и разрешённой operation configuration. Import
намеренно не поддержан.

## Reference Data

Reference Data независимо версионирует Routes и Airport Other Costs. У маршрута
есть вылет, посадка, расстояние и полётное время; его канонический ключ
вычисляется из этих данных и уникален. Airport Other Costs используют уникальный
аэропорт и неотрицательную сумму. Базовый набор v1 содержит 500 маршрутов и 45
Airport Other Costs.

Draft-версии Reference Data имеют тот же жизненный цикл validate, compare,
preview, activate и rollback, что и Configuration. Активация Reference Data
независима от Configuration и не меняет `data_revision`. UI `/admin` до
сохранения редактирует только in-memory полный payload draft; активные записи
остаются доступными только для чтения.

## Live-источники и ручные данные

SRV и Fuel Registry — операционные настройки источников, а не Calculation
Configuration. Через UI источников можно управлять их директорией, mask,
активным файлом и статусом обновления. Ручные тарифы дополняют отсутствующие
ключи; при конфликте импортированные тарифы сохраняют приоритет.

В навигации `/admin` Routes/ИШР и Airport Other Costs/«Прочее» видны как
«Справочники», но остаются в собственном lifecycle Reference Data. SRV/ЦРТ и
Fuel Registry/«Выгрузка 1С» остаются в Sources и не становятся Configuration.

Массовый импорт Reference Data из CSV/XLSX, перенос source/audit в `/admin` и
новые возможности расчёта требуют изменения будущего релиза.
