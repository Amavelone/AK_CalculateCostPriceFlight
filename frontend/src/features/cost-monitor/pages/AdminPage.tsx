import { useEffect, useMemo, useState } from 'react'
import type {
  ActiveConfiguration,
  CalculationResult,
  ConfigurationComparison,
  ConfigurationVersion,
  JsonValue,
} from '../types'

interface AdminPageProps {
  active: ActiveConfiguration | null
  versions: ConfigurationVersion[]
  comparison: ConfigurationComparison | null
  result: CalculationResult | null
  loading: boolean
  compareLoading: boolean
  onRefresh: () => void
  onCompare: (leftVersion: number, rightVersion: number) => void
}

const number = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 3 })

function dateTime(value: string | null): string {
  return value ? new Date(value).toLocaleString('ru-RU') : '—'
}

function valueText(value: JsonValue): string {
  if (value === null) return '—'
  if (typeof value === 'number') return number.format(value)
  if (typeof value === 'string' || typeof value === 'boolean') return String(value)
  return JSON.stringify(value, null, 2)
}

function Parameter({ label, value, unit }: { label: string; value: number | string; unit?: string }) {
  return <div className="admin-parameter"><span>{label}</span><b>{typeof value === 'number' ? number.format(value) : value}{unit ? ` ${unit}` : ''}</b></div>
}

export function AdminPage({ active, versions, comparison, result, loading, compareLoading, onRefresh, onCompare }: AdminPageProps) {
  const orderedVersions = useMemo(() => [...versions].sort((left, right) => left.version - right.version), [versions])
  const [leftVersion, setLeftVersion] = useState<number | null>(null)
  const [rightVersion, setRightVersion] = useState<number | null>(null)

  useEffect(() => {
    if (!orderedVersions.length) {
      setLeftVersion(null)
      setRightVersion(null)
      return
    }
    const latest = orderedVersions.at(-1)?.version ?? null
    const previous = orderedVersions.at(-2)?.version ?? latest
    setLeftVersion((current) => current && orderedVersions.some((item) => item.version === current) ? current : previous)
    setRightVersion((current) => current && orderedVersions.some((item) => item.version === current) ? current : latest)
  }, [orderedVersions])

  if (loading && !active) return <div className="loading-card">Загружаем административные данные…</div>
  if (!active) return <div className="information-card admin-unavailable"><div><b>Configuration недоступна</b><p>Обновите данные или проверьте доступность backend API.</p></div><button className="button button-secondary" onClick={onRefresh}>Повторить</button></div>

  const configuration = active.configuration
  const scenarioRows = Object.entries(configuration.initial_data.scenario_rates).flatMap(([scenario, aircraftRates]) =>
    Object.entries(aircraftRates).map(([aircraft, rates]) => ({ scenario, aircraft, rates })),
  )

  return (
    <section className="page-stack admin-page">
      <section className="admin-toolbar">
        <div><span className="read-only-badge">Только чтение</span><p>Версии и правила отображаются без возможности изменения или активации.</p></div>
        <button className="button button-secondary" disabled={loading} onClick={onRefresh}>{loading ? 'Обновляем…' : '↻ Обновить'}</button>
      </section>

      <section className="admin-summary-grid">
        <article className="admin-summary-card"><span>Активная версия</span><b>v{active.version}</b><small>{active.state === 'active' ? 'Используется расчётом' : active.state}</small></article>
        <article className="admin-summary-card"><span>Validation</span><b className="admin-valid">VALID</b><small>{active.validation_status}</small></article>
        <article className="admin-summary-card"><span>Версия схемы</span><b>{configuration.schema_version}</b><small>Code-owned definition</small></article>
        <article className="admin-summary-card"><span>Ревизия данных</span><b>{result?.data_snapshot.revision ?? '—'}</b><small>Из текущего расчёта</small></article>
      </section>

      <section className="admin-card">
        <div className="section-heading"><div><h2>Активные параметры</h2><p>Validated runtime configuration, применяемая calculation engine.</p></div><span className="admin-version-chip">v{active.version}</span></div>
        <div className="admin-parameter-groups">
          <article><h3>Топливо и АНО</h3><Parameter label="Расход топлива" value={configuration.fuel.consumption_tons_per_hour} unit="т/ч" /><Parameter label="Маршрутная ставка АНО" value={configuration.ano.route_rate_per_100_km} unit="₽ / 100 км" /></article>
          <article><h3>Бортовое питание</h3><Parameter label="Базовые единицы" value={configuration.catering.base_units} /><Parameter label="Базовая ставка" value={configuration.catering.base_unit_rate} unit="₽" /><Parameter label="Доплата за пассажира" value={configuration.catering.passenger_surcharge} unit="₽" /></article>
          <article><h3>НДС</h3><Parameter label="Ставка" value={`${number.format(configuration.vat.rate * 100)}%`} /><Parameter label="Аэропорты" value={configuration.vat.airports.join(', ')} /></article>
          <article><h3>Наземное обслуживание</h3><Parameter label="Общий делитель" value={configuration.ground.split_divisor} /><Parameter label="Трапы" value={configuration.ground.stairs_units} /><Parameter label="Телетрап" value={configuration.ground.telebridge_minutes} unit="мин" /><Parameter label="Пассажирский блок" value={configuration.ground.transport_passenger_block} /><Parameter label="Пожарная машина" value={configuration.ground.fire_truck_rate} unit="₽" /></article>
        </div>
      </section>

      <section className="admin-grid-two">
        <article className="admin-card">
          <div className="section-heading"><div><h2>Множители ВС</h2><p>Начальные module parameters до обновления workbook.</p></div></div>
          <div className="admin-table-wrap"><table className="admin-table"><thead><tr><th>Тип ВС</th><th>Множитель</th></tr></thead><tbody>{Object.entries(configuration.initial_data.aircraft_multipliers).map(([aircraft, multiplier]) => <tr key={aircraft}><td>{aircraft}</td><td>{number.format(multiplier)}</td></tr>)}</tbody></table></div>
        </article>
        <article className="admin-card">
          <div className="section-heading"><div><h2>Source bindings</h2><p>Code-approved adapters и baseline masks.</p></div></div>
          <div className="admin-table-wrap"><table className="admin-table"><thead><tr><th>Источник</th><th>Parser</th><th>Маска</th></tr></thead><tbody>{configuration.source_bindings.map((binding) => <tr key={binding.id}><td><b>{binding.label}</b><small>{binding.id}</small></td><td>{binding.parser}</td><td><code>{binding.default_mask}</code></td></tr>)}</tbody></table></div>
        </article>
      </section>

      <section className="admin-card">
        <div className="section-heading"><div><h2>Сценарии M1 / M2 / M3</h2><p>Initial scenario rates, входящие в active configuration.</p></div></div>
        <div className="admin-table-wrap"><table className="admin-table"><thead><tr><th>Сценарий</th><th>Тип ВС</th><th>M1</th><th>M2</th><th>M3</th></tr></thead><tbody>{scenarioRows.map(({ scenario, aircraft, rates }) => <tr key={`${scenario}-${aircraft}`}><td>{scenario}</td><td>{aircraft}</td><td>{number.format(rates[0])}</td><td>{number.format(rates[1])}</td><td>{number.format(rates[2])}</td></tr>)}</tbody></table></div>
      </section>

      <section className="admin-card">
        <div className="section-heading"><div><h2>История версий</h2><p>Immutable validated versions и время последней активации.</p></div></div>
        <div className="admin-table-wrap"><table className="admin-table"><thead><tr><th>Версия</th><th>Состояние</th><th>Validation</th><th>Создана</th><th>Активирована</th></tr></thead><tbody>{orderedVersions.map((version) => <tr key={version.version}><td><b>v{version.version}</b></td><td><span className={`admin-state ${version.state}`}>{version.state}</span></td><td>{version.validation_status}</td><td>{dateTime(version.created_at)}</td><td>{dateTime(version.activated_at)}</td></tr>)}</tbody></table></div>
      </section>

      <section className="admin-card">
        <div className="section-heading"><div><h2>Сравнение версий</h2><p>Изменённые configuration paths без изменения active state.</p></div></div>
        {orderedVersions.length < 2 ? <div className="admin-empty">Для сравнения нужна как минимум ещё одна immutable version.</div> : (
          <>
            <div className="admin-compare-controls">
              <label><span>Исходная версия</span><select value={leftVersion ?? ''} onChange={(event) => setLeftVersion(Number(event.target.value))}>{orderedVersions.map((version) => <option key={version.version} value={version.version}>v{version.version}</option>)}</select></label>
              <span className="admin-compare-arrow">→</span>
              <label><span>Сравниваемая версия</span><select value={rightVersion ?? ''} onChange={(event) => setRightVersion(Number(event.target.value))}>{orderedVersions.map((version) => <option key={version.version} value={version.version}>v{version.version}</option>)}</select></label>
              <button className="button button-secondary" disabled={compareLoading || leftVersion === null || rightVersion === null || leftVersion === rightVersion} onClick={() => leftVersion !== null && rightVersion !== null && onCompare(leftVersion, rightVersion)}>{compareLoading ? 'Сравниваем…' : 'Сравнить'}</button>
            </div>
            {comparison ? comparison.changes.length ? <div className="admin-table-wrap"><table className="admin-table"><thead><tr><th>Path</th><th>Было</th><th>Стало</th></tr></thead><tbody>{comparison.changes.map((change) => <tr key={change.path}><td><code>{change.path}</code></td><td><pre>{valueText(change.before)}</pre></td><td><pre>{valueText(change.after)}</pre></td></tr>)}</tbody></table></div> : <div className="admin-empty">Выбранные версии не отличаются.</div> : null}
          </>
        )}
      </section>

      <section className="admin-card">
        <div className="section-heading"><div><h2>Calculation trace</h2><p>Фактические inputs, lookups, параметры, operations и результаты текущего расчёта.</p></div>{result && <span className="admin-version-chip">config v{result.trace.config_version} · data r{result.trace.data_revision}</span>}</div>
        {!result ? <div className="admin-empty">Trace появится после выполнения текущего расчёта.</div> : result.trace.legs.map((leg, index) => (
          <details className="admin-trace-leg" key={leg.leg_id} open={index === 0}>
            <summary>Плечо {leg.leg_id} <span>{leg.steps.length} шагов</span></summary>
            <div className="admin-trace-steps">{leg.steps.map((step, stepIndex) => <article key={`${step.stage}-${step.component}-${stepIndex}`}><span className={`trace-stage ${step.stage}`}>{step.stage}</span><div><b>{step.component}</b>{step.operation && <small>operation: {step.operation}</small>}</div><pre>{JSON.stringify(step.values, null, 2)}</pre></article>)}</div>
          </details>
        ))}
      </section>
    </section>
  )
}
