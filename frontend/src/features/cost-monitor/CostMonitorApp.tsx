import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from './api'
import { CalculatorPage } from './pages/CalculatorPage'
import { SettingsPage } from './pages/SettingsPage'
import { SourcesPage } from './pages/SourcesPage'
import { TariffsPage } from './pages/TariffsPage'
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
  const calculationRequestId = useRef(0)
  const calculationAbort = useRef<AbortController | null>(null)

  const runCalculation = async (nextCalculation: CalculationRequest) => {
    const requestId = ++calculationRequestId.current
    calculationAbort.current?.abort()
    const controller = new AbortController()
    calculationAbort.current = controller
    try {
      const nextResult = await api.calculate(nextCalculation, controller.signal)
      if (requestId === calculationRequestId.current) setResult(nextResult)
      return nextResult
    } finally {
      if (requestId === calculationRequestId.current) calculationAbort.current = null
    }
  }

  const refreshTariffs = async (search = tariffSearch) => {
    const data = await api.tariffs(search)
    setTariffs(data)
  }

  const synchronizeCalculationData = async () => {
    const [nextTariffs, nextOptions] = await Promise.all([
      api.tariffs(tariffSearch),
      api.calculationOptions(),
    ])
    setTariffs(nextTariffs)
    setOptions(nextOptions)
    await runCalculation(calculation)
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
      void Promise.all([api.saveDraft(calculation), runCalculation(calculation)])
        .catch((caught) => {
          if (caught instanceof DOMException && caught.name === 'AbortError') return
          setError(caught instanceof Error ? caught.message : 'Не удалось сохранить расчет')
        })
        .finally(() => setIsSaving(false))
    }, 350)
    return () => window.clearTimeout(timer)
  }, [calculation, isReady])

  useEffect(() => () => calculationAbort.current?.abort(), [])

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

export default App
