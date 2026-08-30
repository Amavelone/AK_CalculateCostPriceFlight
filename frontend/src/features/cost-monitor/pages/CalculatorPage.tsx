import { useState } from 'react'
import { money, quantity } from '../formatting'
import type { CalculationOptions, CalculationRequest, CalculationResult, ExportFormat, LegInput } from '../types'

type CostComponentKey = 'fuel' | 'ground' | 'ano' | 'catering' | 'vat'
type CalculatedLeg = CalculationResult['legs'][number]

const componentNames: Array<[CostComponentKey, string]> = [
  ['fuel', 'ГСМ'],
  ['ground', 'Наземное обслуживание'],
  ['ano', 'АНО'],
  ['catering', 'Бортпитание'],
  ['vat', 'НДС'],
]

interface CalculatorPageProps {
  calculation: CalculationRequest
  result: CalculationResult | null
  options: CalculationOptions
  summary: Record<string, number>
  isSaving: boolean
  onSettings: (patch: Partial<CalculationRequest['settings']>) => void
  onLegChange: (id: string, patch: Partial<LegInput>) => void
  onRemoveLeg: (id: string) => void
  onAddLeg: () => void
  onExport: (format: ExportFormat) => void
  exporting: ExportFormat | null
}

export function CalculatorPage({ calculation, result, options, summary, onSettings, onLegChange, onRemoveLeg, onAddLeg, onExport, exporting }: CalculatorPageProps) {
  const resultById = new Map(result?.legs.map((item) => [item.id, item]) ?? [])
  const scenarios = Array.from(new Set([...options.scenarios, calculation.settings.scenario]))
  const [expandedComponents, setExpandedComponents] = useState<Record<string, boolean>>({})
  const totalFlightTime = result?.legs.reduce((total, leg) => total + leg.flight_time, 0) ?? 0
  const totalFuelTons = result?.legs.reduce((total, leg) => total + leg.fuel_tons, 0) ?? 0

  const toggleComponent = (legId: string, component: CostComponentKey) => {
    const id = `${legId}-${component}`
    setExpandedComponents((current) => ({ ...current, [id]: !current[id] }))
  }

  return (
    <section className="page-stack">
      <div className="control-card">
        <div className="section-heading compact-heading">
          <div>
            <h2>Параметры расчета</h2>
            <p>Настройки применяются ко всем введенным плечам.</p>
          </div>
          <label className="switch-line">
            <span>Детализация</span>
            <input type="checkbox" checked={calculation.settings.show_details} onChange={(event) => onSettings({ show_details: event.target.checked })} />
            <span className="switch" />
          </label>
        </div>
        <div className="control-grid">
          <label className="field">
            <span>Сценарий ЛЧ</span>
            <select value={calculation.settings.scenario} onChange={(event) => onSettings({ scenario: event.target.value })}>
              {scenarios.map((scenario) => <option key={scenario}>{scenario}</option>)}
            </select>
          </label>
          <div className="field">
            <span>Источник ГСМ</span>
            <div className="segmented">
              {(['ЦРТ', 'АК'] as const).map((source) => (
                <button key={source} className={calculation.settings.fuel_source === source ? 'selected' : ''} onClick={() => onSettings({ fuel_source: source })}>
                  {source}
                </button>
              ))}
            </div>
          </div>
          <label className="field switch-field">
            <span>Доплата за пассажиров</span>
            <div className="toggle-caption">
              <input type="checkbox" checked={calculation.settings.catering} onChange={(event) => onSettings({ catering: event.target.checked })} />
              <span className="switch" />
              <b>{calculation.settings.catering ? 'Включено' : 'Не включено'}</b>
            </div>
          </label>
        </div>
      </div>

      <section className="export-card">
        <span className="export-icon" aria-hidden="true">⇩</span>
        <div className="export-copy">
          <h2>Экспорт результата</h2>
          <p>Параметры, плечи, компоненты, детализация и общие итоги в одном снимке расчёта.</p>
        </div>
        <div className="export-actions">
          <button className="button button-quiet" disabled={!result || exporting !== null} onClick={() => onExport('json')}>{exporting === 'json' ? 'Готовим…' : 'JSON'}</button>
          <button className="button button-primary" disabled={!result || exporting !== null} onClick={() => onExport('xlsx')}>{exporting === 'xlsx' ? 'Готовим…' : 'Excel'}</button>
        </div>
      </section>

      <div className="calculator-layout">
        <section className="legs-card">
          <div className="section-heading">
            <div>
              <h2>Плечи маршрута</h2>
              <p>Добавляйте столько плеч, сколько нужно для расчета.</p>
            </div>
            <button className="button button-primary" onClick={onAddLeg}>＋ Добавить плечо</button>
          </div>
          <div className="leg-list">
            {calculation.legs.map((leg, index) => {
              const item = resultById.get(leg.id)
              return (
                <article className="leg-card" key={leg.id}>
                  <div className="leg-number">{index + 1}</div>
                  <div className="leg-fields">
                    <label className="field">
                      <span>Вылет</span>
                      <input value={leg.departure} maxLength={3} placeholder="IATA" onChange={(event) => onLegChange(leg.id, { departure: event.target.value.toUpperCase() })} />
                    </label>
                    <span className="route-arrow">→</span>
                    <label className="field">
                      <span>Посадка</span>
                      <input value={leg.arrival} maxLength={3} placeholder="IATA" onChange={(event) => onLegChange(leg.id, { arrival: event.target.value.toUpperCase() })} />
                    </label>
                    <label className="field field-aircraft">
                      <span>Тип ВС</span>
                      <select value={leg.aircraft} onChange={(event) => onLegChange(leg.id, { aircraft: event.target.value })}>
                        {Array.from(new Set([...options.aircraft, leg.aircraft])).map((aircraft) => <option key={aircraft}>{aircraft}</option>)}
                      </select>
                    </label>
                    <label className="field field-passengers">
                      <span>Пассажиры</span>
                      <input type="number" min="0" value={leg.passengers} onChange={(event) => onLegChange(leg.id, { passengers: Number(event.target.value) || 0 })} />
                    </label>
                  </div>
                  <div className="leg-actions">
                    <button
                      className={`techstop-button ${calculation.settings.techstop_leg_id === leg.id ? 'selected' : ''}`}
                      onClick={() => onSettings({ techstop_leg_id: calculation.settings.techstop_leg_id === leg.id ? null : leg.id })}
                    >
                      Техстоп
                    </button>
                    <button className="icon-button" disabled={calculation.legs.length === 1} onClick={() => onRemoveLeg(leg.id)} aria-label="Удалить плечо">×</button>
                  </div>
                  {item && (
                    <div className="leg-meta">
                      <span>{item.route} · {item.flight_time.toLocaleString('ru-RU')} ч</span>
                      <strong className="leg-margins">
                        <span>М1: {money(item.totals.m1)} ₽</span>
                        <span>М2: {money(item.totals.m2)} ₽</span>
                        <span>М3: {money(item.totals.m3)} ₽</span>
                      </strong>
                    </div>
                  )}
                </article>
              )
            })}
          </div>
        </section>

        <aside className="summary-card">
          <div className="summary-title">
            <span className="summary-icon">◈</span>
            <div><h2>Итог расчета</h2><p>По всем плечам</p></div>
          </div>
          <SummaryRow label="Итого М1" value={summary.m1} />
          <SummaryRow label="Итого М2" value={summary.m2} highlighted />
          <SummaryRow label="Итого М3" value={summary.m3} />
          <div className="summary-footer">
            <span>Плеч в расчете</span><b>{calculation.legs.length}</b>
          </div>
          <div className="summary-extra">
            <div className="summary-extra-row"><span>Летное время</span><b>{quantity(totalFlightTime)} ч</b></div>
            <div className="summary-extra-row"><span>ГСМ, тонн</span><b>{quantity(totalFuelTons)} т</b></div>
          </div>
        </aside>
      </div>

      {result?.warnings.length ? (
        <div className="warning-card">
          <b>Нужно проверить данные</b>
          <ul>{result.warnings.slice(0, 6).map((warning) => <li key={warning}>{warning}</li>)}</ul>
        </div>
      ) : null}

      {calculation.settings.show_details && result && (
        <section className="details-section">
          <div className="section-heading"><div><h2>Компоненты себестоимости</h2><p>Раскладка по каждому плечу. Откройте компонент, чтобы посмотреть уже учтённые составляющие.</p></div></div>
          <div className="detail-grid">
            {result.legs.map((leg) => (
              <article className="detail-card" key={leg.id}>
                <div className="detail-heading"><b>{leg.route || 'Новое плечо'}</b><span>{leg.line_type}{leg.is_techstop ? ' · техстоп' : ''}</span></div>
                {componentNames.map(([key, label]) => {
                  const componentId = `${leg.id}-${key}`
                  const isExpanded = Boolean(expandedComponents[componentId])
                  return (
                    <div className="component-block" key={key}>
                      <button className={`component-row component-trigger ${isExpanded ? 'expanded' : ''}`} type="button" onClick={() => toggleComponent(leg.id, key)} aria-expanded={isExpanded}>
                        <span className="component-label"><i className="component-chevron" aria-hidden="true">⌄</i>{label}</span>
                        <b>{money(leg.components[key])} ₽</b>
                      </button>
                      {isExpanded && <ComponentBreakdown component={key} leg={leg} />}
                    </div>
                  )
                })}
                <div className="component-row margin-row"><span>М1 / М2 / М3</span><b>{money(leg.components.m1)} / {money(leg.components.m2)} / {money(leg.components.m3)} ₽</b></div>
              </article>
            ))}
          </div>
        </section>
      )}
    </section>
  )
}

function BreakdownRow({ label, description, amount, muted = false }: { label: string; description: string; amount?: number; muted?: boolean }) {
  return (
    <div className={`breakdown-row ${muted ? 'muted' : ''}`}>
      <div><b>{label}</b><span>{description}</span></div>
      {amount === undefined ? <em>Не включено</em> : <strong>{money(amount)} ₽</strong>}
    </div>
  )
}

function ComponentBreakdown({ component, leg }: { component: CostComponentKey; leg: CalculatedLeg }) {
  const rows = leg.details[component]
  return (
    <div className="component-breakdown">
      <p className="breakdown-context">Детализация из расчёта backend для плеча {leg.route || '—'}</p>
      <div className="breakdown-list">
        {rows.length ? rows.map((item, index) => (
          <BreakdownRow key={`${item.service}-${index}`} label={item.service} description={`Ставка: ${money(item.rate)} ₽ · объём: ${quantity(item.volume)} · делитель: ${quantity(item.divisor ?? 1)}`} amount={item.amount} />
        )) : <BreakdownRow label="Компонент" description="В расчёте нет применимых строк детализации" muted />}
      </div>
    </div>
  )
}

function SummaryRow({ label, value, highlighted = false }: { label: string; value: number; highlighted?: boolean }) {
  return <div className={`summary-row ${highlighted ? 'highlighted' : ''}`}><span>{label}</span><b>{money(value)} ₽</b></div>
}
