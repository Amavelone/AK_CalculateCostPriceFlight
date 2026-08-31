import { useEffect, useState } from 'react'
import { api } from './api'
import { AdminPage } from './pages/AdminPage'
import type {
  ActiveConfiguration,
  CalculationRequest,
  ConfigurationCapabilities,
  ConfigurationComparison,
  ConfigurationDraft,
  ConfigurationPreviewComparison,
  ConfigurationVersion,
  CostMonitorConfiguration,
} from './types'

const ADMIN_DRAFT_KEY = 'cost-monitor-admin-draft-version-v2'

const controlCalculation: CalculationRequest = {
  legs: [{ id: 'control-leg', departure: 'DME', arrival: 'KJA', aircraft: '738', passengers: 150 }],
  settings: {
    scenario: 'ГБ 2026',
    fuel_source: 'ЦРТ',
    techstop_leg_id: null,
    catering: true,
    show_details: true,
  },
}

export default function AdminApp() {
  const [active, setActive] = useState<ActiveConfiguration | null>(null)
  const [versions, setVersions] = useState<ConfigurationVersion[]>([])
  const [capabilities, setCapabilities] = useState<ConfigurationCapabilities | null>(null)
  const [draft, setDraft] = useState<ConfigurationDraft | null>(null)
  const [configuration, setConfiguration] = useState<CostMonitorConfiguration | null>(null)
  const [comparison, setComparison] = useState<ConfigurationComparison | null>(null)
  const [preview, setPreview] = useState<ConfigurationPreviewComparison | null>(null)
  const [calculation, setCalculation] = useState<CalculationRequest>(controlCalculation)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const refresh = async () => {
    const [nextActive, nextVersions, nextCapabilities] = await Promise.all([
      api.activeConfiguration(),
      api.configurationVersions(),
      api.configurationCapabilities(),
    ])
    setActive(nextActive)
    setVersions(nextVersions)
    setCapabilities(nextCapabilities)
  }

  useEffect(() => {
    let mounted = true
    async function bootstrap() {
      try {
        await refresh()
        const savedVersion = Number(window.localStorage.getItem(ADMIN_DRAFT_KEY))
        if (savedVersion) {
          try {
            const savedDraft = await api.configurationDraft(savedVersion)
            if (mounted) {
              setDraft(savedDraft)
              setConfiguration(savedDraft.configuration)
            }
          } catch {
            window.localStorage.removeItem(ADMIN_DRAFT_KEY)
          }
        }
      } catch (caught) {
        if (mounted) setError(caught instanceof Error ? caught.message : 'Не удалось загрузить admin configuration')
      } finally {
        if (mounted) setLoading(false)
      }
    }
    void bootstrap()
    return () => { mounted = false }
  }, [])

  const run = async (name: string, operation: () => Promise<void>) => {
    setBusy(name)
    setError(null)
    setNotice(null)
    try {
      await operation()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Административная операция завершилась ошибкой')
    } finally {
      setBusy(null)
    }
  }

  const createDraft = () => run('create', async () => {
    const next = await api.createConfigurationDraft()
    setDraft(next)
    setConfiguration(next.configuration)
    setPreview(null)
    setComparison(null)
    window.localStorage.setItem(ADMIN_DRAFT_KEY, String(next.version))
    setNotice(`Создан draft v${next.version}`)
  })

  const saveDraft = async (): Promise<ConfigurationDraft> => {
    if (!draft || !configuration) throw new Error('Сначала создайте draft')
    const saved = await api.updateConfigurationDraft(draft.version, configuration)
    setDraft(saved)
    setConfiguration(saved.configuration)
    return saved
  }

  const save = () => run('save', async () => {
    const saved = await saveDraft()
    setNotice(`Draft v${saved.version} сохранён`)
  })

  const validate = () => run('validate', async () => {
    const saved = await saveDraft()
    const validated = await api.validateConfigurationDraft(saved.version)
    setDraft(validated)
    setNotice(`Draft v${validated.version}: VALID`)
  })

  const previewDraft = () => run('preview', async () => {
    const saved = await saveDraft()
    setPreview(await api.previewConfigurationDraft(saved.version, calculation))
    setNotice('Preview рассчитан без изменения active configuration')
  })

  const activate = () => run('activate', async () => {
    const saved = await saveDraft()
    await api.validateConfigurationDraft(saved.version)
    await api.activateConfigurationDraft(saved.version)
    window.localStorage.removeItem(ADMIN_DRAFT_KEY)
    setDraft(null)
    setConfiguration(null)
    setPreview(null)
    await refresh()
    setNotice(`Configuration v${saved.version} активирована`)
  })

  const rollback = (version: number) => run('rollback', async () => {
    await api.rollbackConfiguration(version)
    setPreview(null)
    await refresh()
    setNotice(`Выполнен rollback на v${version}`)
  })

  const compare = (left: number, right: number) => run('compare', async () => {
    setComparison(await api.compareConfigurations(left, right))
  })

  return (
    <div className="admin-shell">
      {notice && <div className="toast toast-success" onClick={() => setNotice(null)}>{notice}<button aria-label="Закрыть">×</button></div>}
      {error && <div className="toast toast-error" onClick={() => setError(null)}>{error}<button aria-label="Закрыть">×</button></div>}
      <AdminPage
        active={active}
        versions={versions}
        capabilities={capabilities}
        draft={draft}
        configuration={configuration}
        comparison={comparison}
        preview={preview}
        calculation={calculation}
        loading={loading}
        busy={busy}
        onConfigurationChange={setConfiguration}
        onCalculationChange={setCalculation}
        onCreateDraft={createDraft}
        onSave={save}
        onValidate={validate}
        onPreview={previewDraft}
        onActivate={activate}
        onRollback={rollback}
        onCompare={compare}
      />
    </div>
  )
}
