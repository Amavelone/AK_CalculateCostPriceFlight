import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { api } from './api'
import type { CalculationOptions, CalculationRequest, CalculationResult, ExportFormat, LegInput, SourceConfig, Tariff } from './types'

type Page = 'calculate' | 'sources' | 'tariffs' | 'settings'

const LOCAL_DRAFT_KEY = 'cost-monitor-calculation-draft-v1'

const initialCalculation: CalculationRequest = {
  legs: [{ id: 'leg-1', departure: '', arrival: '', aircraft: '738', passengers: 0 }],
  settings: {
    scenario: 'ГБ 2026',
    fuel_source: 'ЦРТ',
    techstop_leg_id: null,
    catering: false,
    show_details: true,
  },
}

const initialOptions: CalculationOptions = {
  scenarios: ['ГБ 2026', 'Оперативная 2026'],
  aircraft: ['733', '737', '738'],
}

const pageMeta: Record<Page, { label: string; icon: string; subtitle: string }> = {
  calculate: { label: 'Расчет', icon: '◈', subtitle: 'Себестоимость маршрута' },
  sources: { label: 'Источники', icon: '↻', subtitle: 'Файлы и обновление данных' },
  tariffs: { label: 'Подключённые услуги', icon: '⊞', subtitle: 'Тарифы аэропортов' },
  settings: { label: 'Параметры', icon: '⚙', subtitle: 'Пути и правила источников' },
}

type CostComponentKey = 'fuel' | 'ground' | 'ano' | 'catering' | 'vat'
type CalculatedLeg = CalculationResult['legs'][number]

const componentNames: Array<[CostComponentKey, string]> = [
  ['fuel', 'ГСМ'],
  ['ground', 'Наземное обслуживание'],
  ['ano', 'АНО'],
  ['catering', 'Бортпитание'],
  ['vat', 'НДС'],
]

function money(value: number | undefined): string {
  return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(value ?? 0)
}

function quantity(value: number | undefined): string {
  return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 3 }).format(value ?? 0)
}

function timeText(value: string | null): string {
  if (!value) return 'Еще не обновлялся'
  return new Intl.DateTimeFormat('ru-RU', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(value))
}

function createLeg(): LegInput {
  return { id: `leg-${crypto.randomUUID()}`, departure: '', arrival: '', aircraft: '738', passengers: 0 }
}

function readLocalDraft(): CalculationRequest | null {
  try {
    const data = window.localStorage.getItem(LOCAL_DRAFT_KEY)
    return data ? (JSON.parse(data) as CalculationRequest) : null
  } catch {
    return null
  }
}

function App() {
  const [page, setPage] = useState<Page>('calculate')
  const [calculation, setCalculation] = useState<CalculationRequest>(initialCalculation)
  const [result, setResult] = useState<CalculationResult | null>(null)
  const [options, setOptions] = useState<CalculationOptions>(initialOptions)
  const [sources, setSources] = useState<SourceConfig[]>([])
  const [tariffs, setTariffs] = useState<Tariff[]>([])
  const [tariffSearch, setTariffSearch] = useState('')
  const [isReady, setIsReady] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [busySource, setBusySource] = useState<string | null>(null)
  const [exporting, setExporting] = useState<ExportFormat | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refreshTariffs = async (search = tariffSearch) => {
    const data = await api.tariffs(search)
    setTariffs(data)
  }

  const synchronizeCalculationData = async () => {
    const [nextTariffs, nextOptions, nextResult] = await Promise.all([
      api.tariffs(tariffSearch),
      api.calculationOptions(),
      api.calculate(calculation),
    ])
    setTariffs(nextTariffs)
    setOptions(nextOptions)
    setResult(nextResult)
  }

  useEffect(() => {
    let active = true
    async function bootstrap() {
      try {
        const [draft, loadedSources, loadedTariffs, calculationOptions] = await Promise.all([
          api.getDraft(),
          api.sources(),
          api.tariffs(),
          api.calculationOptions(),
        ])
        if (!active) return
        setCalculation(readLocalDraft() ?? draft.calculation ?? initialCalculation)
        setSources(loadedSources)
        setTariffs(loadedTariffs)
        setOptions(calculationOptions)
      } catch (caught) {
        if (active) setError(caught instanceof Error ? caught.message : 'Не удалось загрузить данные приложения')
      } finally {
        if (active) setIsReady(true)
      }
    }
    void bootstrap()
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    if (!isReady) return
    window.localStorage.setItem(LOCAL_DRAFT_KEY, JSON.stringify(calculation))
    const timer = window.setTimeout(() => {
      setIsSaving(true)
      void Promise.all([api.saveDraft(calculation), api.calculate(calculation)])
        .then(([, nextResult]) => setResult(nextResult))
        .catch((caught) => setError(caught instanceof Error ? caught.message : 'Не удалось сохранить расчет'))
        .finally(() => setIsSaving(false))
    }, 350)
    return () => window.clearTimeout(timer)
  }, [calculation, isReady])

  useEffect(() => {
    if (!isReady) return
    const timer = window.setTimeout(() => {
      void refreshTariffs(tariffSearch).catch((caught) =>
        setError(caught instanceof Error ? caught.message : 'Не удалось получить тарифы'),
      )
    }, 250)
    return () => window.clearTimeout(timer)
  }, [tariffSearch, isReady])

  const setSettings = (patch: Partial<CalculationRequest['settings']>) => {
    setCalculation((current) => ({ ...current, settings: { ...current.settings, ...patch } }))
  }

  const updateLeg = (id: string, patch: Partial<LegInput>) => {
    setCalculation((current) => ({
      ...current,
      legs: current.legs.map((leg) => (leg.id === id ? { ...leg, ...patch } : leg)),
    }))
  }

  const exportCalculation = async (format: ExportFormat) => {
    setExporting(format)
    setError(null)
    try {
      const file = await api.exportCalculation(format, calculation)
      const link = document.createElement('a')
      link.href = URL.createObjectURL(file.blob)
      link.download = file.filename
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.setTimeout(() => URL.revokeObjectURL(link.href), 0)
      setNotice(`Выгрузка «${file.filename}» готова`)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Не удалось сформировать выгрузку')
    } finally {
      setExporting(null)
    }
  }

  const removeLeg = (id: string) => {
    setCalculation((current) => {
      if (current.legs.length === 1) return current
      return {
        ...current,
        legs: current.legs.filter((leg) => leg.id !== id),
        settings: {
          ...current.settings,
          techstop_leg_id: current.settings.techstop_leg_id === id ? null : current.settings.techstop_leg_id,
        },
      }
    })
  }

  const refreshOne = async (sourceId: string) => {
    setBusySource(sourceId)
    setError(null)
    try {
      const source = await api.refreshSource(sourceId)
      setSources((current) => current.map((item) => (item.id === sourceId ? source : item)))
      if (source.last_status === 'error') {
        setError(`Источник «${source.label}» не обновлен: ${source.last_error ?? 'неизвестная ошибка'}`)
      } else {
        await synchronizeCalculationData()
        setNotice(`Источник «${source.label}» обновлен`)
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Не удалось обновить источник')
    } finally {
      setBusySource(null)
    }
  }

  const refreshAll = async () => {
    setBusySource('all')
    setError(null)
    try {
      const response = await api.refreshAll()
      setSources(response.sources)
      const failed = response.sources.filter((source) => source.last_status === 'error')
      if (response.sources.some((source) => source.last_status === 'ready')) {
        await synchronizeCalculationData()
      }
      if (failed.length) {
        setError(`Не обновились источники: ${failed.map((source) => source.label).join(', ')}`)
      } else {
        setNotice('Обновление источников завершено')
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Не удалось обновить источники')
    } finally {
      setBusySource(null)
    }
  }

  const updateSource = async (source: SourceConfig) => {
    setBusySource(source.id)
    try {
      const saved = await api.updateSource(source.id, source.directory, source.mask)
      setSources((current) => current.map((item) => (item.id === saved.id ? saved : item)))
      setNotice(`Настройки «${saved.label}» сохранены`)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Не удалось сохранить настройки источника')
    } finally {
      setBusySource(null)
    }
  }

  const upload = async (source: SourceConfig, file: File) => {
    setBusySource(source.id)
    try {
      const saved = await api.uploadSource(source.id, file)
      setSources((current) => current.map((item) => (item.id === saved.id ? saved : item)))
      setNotice(`Файл ${file.name} загружен. Теперь обновите источник для парсинга.`)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Не удалось загрузить файл')
    } finally {
      setBusySource(null)
    }
  }

  const summary = useMemo(
    () => ({
      m1: result?.total.m1 ?? 0,
      m2: result?.total.m2 ?? 0,
      m3: result?.total.m3 ?? 0,
    }),
    [result],
  )

  const content = {
    calculate: (
      <CalculatorPage
        calculation={calculation}
        result={result}
        options={options}
        summary={summary}
        isSaving={isSaving}
        onSettings={setSettings}
        onLegChange={updateLeg}
        onRemoveLeg={removeLeg}
        onAddLeg={() => setCalculation((current) => ({ ...current, legs: [...current.legs, createLeg()] }))}
        onExport={exportCalculation}
        exporting={exporting}
      />
    ),
    sources: (
      <SourcesPage
        sources={sources}
        busySource={busySource}
        onRefreshOne={refreshOne}
        onRefreshAll={refreshAll}
        onUpload={upload}
      />
    ),
    tariffs: <TariffsPage tariffs={tariffs} search={tariffSearch} onSearch={setTariffSearch} onDataChanged={synchronizeCalculationData} onError={setError} onNotice={setNotice} />,
    settings: <SettingsPage sources={sources} busySource={busySource} onChange={setSources} onSave={updateSource} />,
  }[page]

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">◌</div>
          <div>
            <strong>Себестоимость</strong>
            <span>Монитор рейсов</span>
          </div>
        </div>
        <nav className="navigation" aria-label="Основная навигация">
          {(Object.keys(pageMeta) as Page[]).map((key) => (
            <button key={key} className={`nav-item ${page === key ? 'active' : ''}`} onClick={() => setPage(key)}>
              <span className="nav-icon">{pageMeta[key].icon}</span>
              {pageMeta[key].label}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <span className="status-dot" />
          Черновик сохраняется
        </div>
      </aside>

      <main className="main-content">
        <header className="page-header">
          <div>
            <p className="eyebrow">Монитор расчета себестоимости</p>
            <h1>{pageMeta[page].label}</h1>
            <p className="page-subtitle">{pageMeta[page].subtitle}</p>
          </div>
          <div className="header-state">
            <span className={`save-indicator ${isSaving ? 'saving' : ''}`} />
            {isSaving ? 'Сохраняем изменения…' : 'Все изменения сохранены'}
          </div>
        </header>

        {notice && <div className="toast toast-success" onClick={() => setNotice(null)}>{notice}<button aria-label="Закрыть">×</button></div>}
        {error && <div className="toast toast-error" onClick={() => setError(null)}>{error}<button aria-label="Закрыть">×</button></div>}
        {!isReady ? <div className="loading-card">Подготавливаем рабочее пространство…</div> : content}
      </main>
    </div>
  )
}

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

function CalculatorPage({ calculation, result, options, summary, onSettings, onLegChange, onRemoveLeg, onAddLeg, onExport, exporting }: CalculatorPageProps) {
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
          <div className="snapshot">
            <span>Снимок данных</span>
            <b>{result ? `Версия ${result.data_snapshot.revision ?? 0} · ${result.data_snapshot.tariffs} тарифов · ${result.data_snapshot.routes} маршрутов` : 'Сохраненный черновик'}</b>
          </div>
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
                      {isExpanded && <ComponentBreakdown component={key} leg={leg} settings={calculation.settings} />}
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

function ComponentBreakdown({ component, leg, settings }: { component: CostComponentKey; leg: CalculatedLeg; settings: CalculationRequest['settings'] }) {
  if (component === 'fuel') {
    return (
      <div className="component-breakdown">
        <p className="breakdown-context">Источник: <b>{settings.fuel_source}</b> · расход: <b>{quantity(leg.fuel_tons)} т</b></p>
        <div className="breakdown-list">
          {leg.details.fuel.length ? leg.details.fuel.map((item) => (
            <BreakdownRow key={item.service} label={item.service} description={`${money(item.rate)} ₽ за т × ${quantity(item.volume)} т`} amount={item.amount} />
          )) : <BreakdownRow label="Тариф ГСМ" description="Для аэропорта не найдена ставка из выбранного источника" muted />}
        </div>
      </div>
    )
  }

  if (component === 'ground') {
    return (
      <div className="component-breakdown">
        <p className="breakdown-context">Услуги, учтённые для плеча {leg.route || '—'}</p>
        <div className="breakdown-list">
          {leg.details.ground.length ? leg.details.ground.map((item, index) => (
            <BreakdownRow key={`${item.service}-${index}`} label={item.service} description={`Ставка: ${money(item.rate)} ₽ · объём: ${quantity(item.volume)}`} amount={item.amount} />
          )) : <BreakdownRow label="Наземные услуги" description="Для аэропорта не найдены применимые тарифы" muted />}
        </div>
      </div>
    )
  }

  if (component === 'ano') {
    const total = leg.components.ano ?? 0
    const routePart = total > 0 ? leg.distance / 100 * 1666.6 : 0
    const airportPart = Math.max(0, total - routePart)
    return (
      <div className="component-breakdown">
        <p className="breakdown-context">Детализация текущей формулы АНО</p>
        <div className="breakdown-list">
          {total > 0 ? <>
            <BreakdownRow label="АНО АД" description={`Ставка аэропорта с коэффициентом типа ВС ${leg.aircraft}`} amount={airportPart} />
            <BreakdownRow label="Маршрутная часть" description={`${quantity(leg.distance)} км ÷ 100 × 1 666,6 ₽`} amount={routePart} />
          </> : <BreakdownRow label="АНО" description="Для плеча отсутствует маршрут или ставка АНО АД" muted />}
        </div>
      </div>
    )
  }

  if (component === 'catering') {
    const total = leg.components.catering ?? 0
    const base = Math.min(total, 9000)
    const passengerExtra = Math.max(0, total - base)
    return (
      <div className="component-breakdown">
        <p className="breakdown-context">Отдельный компонент бортпитания в текущем расчёте</p>
        <div className="breakdown-list">
          {total > 0 ? <BreakdownRow label="Базовая часть" description="6 комплектов × 1 500 ₽" amount={base} /> : <BreakdownRow label="Базовая часть" description="Маршрут не указан — компонент не применяется" muted />}
          {settings.catering ? <BreakdownRow label="Доплата за пассажиров" description={`${leg.passengers} пассажиров × 500 ₽`} amount={passengerExtra} /> : <BreakdownRow label="Доплата за пассажиров" description="Переключатель доплаты выключен" muted />}
        </div>
      </div>
    )
  }

  const total = leg.components.vat ?? 0
  const taxBase = total > 0 ? total / 0.1 : 0
  return (
    <div className="component-breakdown">
      {total > 0 ? <>
        <p className="breakdown-context">НДС применяется к текущей базе для этого плеча</p>
        <div className="breakdown-list">
          <BreakdownRow label="ГСМ в базе НДС" description="Учтённый компонент ГСМ" amount={leg.components.fuel} />
          <BreakdownRow label="Наземное обслуживание в базе" description="Учтённый компонент наземного обслуживания" amount={leg.components.ground} />
          <BreakdownRow label="АНО в базе НДС" description="Учтённый компонент АНО" amount={leg.components.ano} />
          <BreakdownRow label="Бортпитание в базе НДС" description="Учтённый компонент бортпитания" amount={leg.components.catering} />
          <BreakdownRow label="Налоговая база" description="Сумма компонентов выше" amount={taxBase} />
          <BreakdownRow label="Ставка НДС" description="10% от налоговой базы" amount={total} />
        </div>
      </> : <>
        <p className="breakdown-context">НДС для этого плеча не применяется</p>
        <div className="breakdown-list"><BreakdownRow label="Условие НДС" description="Условия текущего расчёта не выполнены" muted /></div>
      </>}
    </div>
  )
}

function SummaryRow({ label, value, highlighted = false }: { label: string; value: number; highlighted?: boolean }) {
  return <div className={`summary-row ${highlighted ? 'highlighted' : ''}`}><span>{label}</span><b>{money(value)} ₽</b></div>
}

interface SourcesPageProps {
  sources: SourceConfig[]
  busySource: string | null
  onRefreshOne: (id: string) => void
  onRefreshAll: () => void
  onUpload: (source: SourceConfig, file: File) => void
}

function SourcesPage({ sources, busySource, onRefreshOne, onRefreshAll, onUpload }: SourcesPageProps) {
  return (
    <section className="page-stack">
      <div className="source-intro">
        <div><h2>Подключенные источники</h2><p>Загрузите новую выгрузку в настроенную папку или обновите данные из уже размещенных файлов.</p></div>
        <button className="button button-primary" onClick={onRefreshAll} disabled={busySource !== null}>{busySource === 'all' ? 'Обновляем…' : '↻ Обновить все'}</button>
      </div>
      <div className="source-grid">
        {sources.map((source) => <SourceCard key={source.id} source={source} busySource={busySource} onRefreshOne={onRefreshOne} onUpload={onUpload} />)}
      </div>
    </section>
  )
}

function SourceCard({ source, busySource, onRefreshOne, onUpload }: { source: SourceConfig; busySource: string | null; onRefreshOne: (id: string) => void; onUpload: (source: SourceConfig, file: File) => void }) {
  const [raw, setRaw] = useState<Array<Record<string, unknown>> | null>(null)
  const [rawFile, setRawFile] = useState<string | null>(null)
  const [rawSheet, setRawSheet] = useState<string | null>(null)
  const [rawSheets, setRawSheets] = useState<string[]>([])
  const [rawError, setRawError] = useState<string | null>(null)
  const [loadingRaw, setLoadingRaw] = useState(false)
  const loadRaw = async (sheet?: string) => {
    if (raw && (!sheet || sheet === rawSheet)) return
    setLoadingRaw(true)
    try {
      const response = await api.rawPreview(source.id, sheet)
      setRaw(response.preview)
      setRawFile(response.file)
      setRawSheet(response.sheet)
      setRawSheets(response.sheets)
      setRawError(null)
    } catch (caught) {
      setRawError(caught instanceof Error ? caught.message : 'Не удалось открыть исходный файл')
    } finally {
      setLoadingRaw(false)
    }
  }
  return <article className="source-card">
    <div className="source-card-head"><div className="source-icon">{source.id === 'fuel_registry' ? '◒' : source.id === 'monitor_workbook' ? '▦' : '↗'}</div><StatusBadge status={source.last_status} /></div>
    <h2>{source.label}</h2><p>{source.description}</p>
    <div className="source-details"><span>Файл</span><b>{source.last_file ?? source.mask}</b><span>Последнее обновление</span><b>{timeText(source.last_updated)}</b><span>Строк загружено</span><b>{source.rows_loaded.toLocaleString('ru-RU')}</b></div>
    {source.last_error && <div className="source-error">{source.last_error}</div>}
    {source.last_note && <div className="source-note">{source.last_note}</div>}
    <div className="source-actions">
      <label className="button button-secondary file-button">Загрузить файл<input type="file" accept=".xlsx" onChange={(event) => { const file = event.target.files?.[0]; if (file) void onUpload(source, file); event.currentTarget.value = '' }} /></label>
      <button className="button button-quiet" disabled={busySource !== null} onClick={() => onRefreshOne(source.id)}>{busySource === source.id ? 'Обновляем…' : 'Обновить'}</button>
    </div>
    <details className="preview" onToggle={(event) => { if ((event.currentTarget as HTMLDetailsElement).open) void loadRaw() }}><summary>{loadingRaw ? 'Открываем исходный файл…' : 'Посмотреть исходные строки'}</summary>{rawError && <div className="source-error">{rawError}</div>}{raw && <><div className="preview-file"><span>{rawFile}</span>{rawSheets.length > 1 && <select aria-label="Лист книги" value={rawSheet ?? ''} onChange={(event) => void loadRaw(event.target.value)}>{rawSheets.map((sheet) => <option key={sheet}>{sheet}</option>)}</select>}</div><PreviewTable rows={raw} /></>}</details>
    {source.preview.length > 0 && <details className="preview"><summary>Посмотреть результат парсинга</summary><PreviewTable rows={source.preview} /></details>}
  </article>
}

function StatusBadge({ status }: { status: SourceConfig['last_status'] }) {
  const labels: Record<SourceConfig['last_status'], string> = { ready: 'Готов', uploaded: 'Загружен', not_updated: 'Не обновлялся', error: 'Ошибка' }
  return <span className={`status-badge ${status}`}>{labels[status]}</span>
}

function PreviewTable({ rows }: { rows: Array<Record<string, unknown>> }) {
  const columns = Object.keys(rows[0] ?? {}).slice(0, 4)
  return <div className="preview-table-wrap"><table className="preview-table"><thead><tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody>{rows.slice(0, 5).map((row, index) => <tr key={index}>{columns.map((column) => <td key={column}>{String(row[column] ?? '—')}</td>)}</tr>)}</tbody></table></div>
}

function TariffsPage({ tariffs, search, onSearch, onDataChanged, onError, onNotice }: { tariffs: Tariff[]; search: string; onSearch: (value: string) => void; onDataChanged: () => Promise<void>; onError: (value: string | null) => void; onNotice: (value: string | null) => void }) {
  const [form, setForm] = useState({ airport: '', service: '', rate: '', unit: 'РУБ-ЕД', aircraft: '', note: '' })
  const [adding, setAdding] = useState(false)
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setAdding(true)
    onError(null)
    try {
      await api.addManualTariff({ ...form, airport: form.airport.toUpperCase(), service: form.service.toUpperCase(), rate: Number(form.rate), aircraft: form.aircraft.toUpperCase() })
      setForm({ airport: '', service: '', rate: '', unit: 'РУБ-ЕД', aircraft: '', note: '' })
      await onDataChanged()
      onNotice('Ручная услуга добавлена в единый справочник')
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : 'Не удалось добавить ручную услугу')
    } finally {
      setAdding(false)
    }
  }
  const remove = async (tariff: Tariff) => {
    if (!window.confirm(`Удалить ручную услугу ${tariff.airport} — ${tariff.service}?`)) return
    try {
      await api.deleteManualTariff(tariff.id)
      await onDataChanged()
      onNotice('Ручная услуга удалена')
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : 'Не удалось удалить услугу')
    }
  }
  return (
    <section className="page-stack">
      <div className="tariff-toolbar"><div><h2>Единый справочник услуг</h2><p>Импортированные тарифы и добавленные вручную значения хранятся вместе.</p></div><label className="search-field"><span>⌕</span><input value={search} onChange={(event) => onSearch(event.target.value)} placeholder="Аэропорт или услуга" /></label></div>
      <form className="manual-form" onSubmit={submit}>
        <div className="form-title"><b>Добавить вручную</b><span>Только для услуги, которой нет в распарсенных источниках.</span></div>
        <label><span>Аэропорт</span><input required maxLength={3} value={form.airport} placeholder="KJA" onChange={(event) => setForm({ ...form, airport: event.target.value.toUpperCase() })} /></label>
        <label className="service-field"><span>Услуга</span><input required value={form.service} placeholder="Например, ВОДА" onChange={(event) => setForm({ ...form, service: event.target.value.toUpperCase() })} /></label>
        <label><span>Ставка</span><input required type="number" min="0" step="0.01" value={form.rate} onChange={(event) => setForm({ ...form, rate: event.target.value })} /></label>
        <label><span>Ед. изм.</span><input value={form.unit} onChange={(event) => setForm({ ...form, unit: event.target.value })} /></label>
        <button className="button button-primary" disabled={adding}>{adding ? 'Добавляем…' : 'Добавить'}</button>
      </form>
      <div className="table-card"><div className="table-caption"><span>Найдено: {tariffs.length.toLocaleString('ru-RU')}</span>{tariffs.length > 200 && <span>Показаны первые 200 строк — уточните поиск.</span>}</div><div className="tariff-table-wrap"><table className="tariff-table"><thead><tr><th>Аэропорт</th><th>Услуга</th><th>Ставка</th><th>Ед. изм.</th><th>Происхождение</th><th /></tr></thead><tbody>{tariffs.slice(0, 200).map((tariff) => <tr key={tariff.id}><td><b>{tariff.airport}</b></td><td>{tariff.service}{tariff.conflict && <span className="conflict-badge">Конфликт</span>}</td><td>{money(tariff.rate)} ₽</td><td>{tariff.unit || '—'}</td><td><span className={`origin ${tariff.source}`}>{tariff.source === 'manual' ? 'Вручную' : tariff.source_file ?? 'Из файла'}</span></td><td>{tariff.source === 'manual' && <button className="delete-link" onClick={() => void remove(tariff)}>Удалить</button>}</td></tr>)}</tbody></table></div></div>
    </section>
  )
}

function SettingsPage({ sources, busySource, onChange, onSave }: { sources: SourceConfig[]; busySource: string | null; onChange: (sources: SourceConfig[]) => void; onSave: (source: SourceConfig) => void }) {
  const edit = (id: string, patch: Partial<SourceConfig>) => onChange(sources.map((source) => source.id === id ? { ...source, ...patch } : source))
  return <section className="page-stack"><div className="settings-intro"><h2>Пути и правила выбора файлов</h2><p>Изменения применятся при следующем обновлении источника. Путь можно направить на прежнюю папку Power Query.</p></div><div className="settings-list">{sources.map((source) => <article className="settings-card" key={source.id}><div><h3>{source.label}</h3><p>{source.description}</p></div><label className="wide-field"><span>Директория</span><input value={source.directory} onChange={(event) => edit(source.id, { directory: event.target.value })} /></label><label><span>Маска файла</span><input value={source.mask} onChange={(event) => edit(source.id, { mask: event.target.value })} /></label><button className="button button-secondary" disabled={busySource !== null} onClick={() => onSave(source)}>{busySource === source.id ? 'Сохраняем…' : 'Сохранить'}</button></article>)}</div><div className="information-card"><b>Как работает хранение</b><p>Черновик расчета сохраняется в браузере и на сервере. Файлы, ручные услуги и пути источников не зависят от кэша браузера.</p></div></section>
}

export default App
