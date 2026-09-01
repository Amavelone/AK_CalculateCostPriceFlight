import { useEffect, useState } from 'react'
import { api } from './api'
import { AdminPage } from './pages/AdminPage'
import { ReferenceDataAdmin } from './pages/ReferenceDataAdmin'
import type {
  ActiveConfiguration,
  ActiveReferenceData,
  CalculationRequest,
  ConfigurationCapabilities,
  ConfigurationComparison,
  ConfigurationDraft,
  ConfigurationPreviewComparison,
  ConfigurationPresentation,
  ConfigurationVersion,
  CostMonitorConfiguration,
  ReferenceDataComparison,
  ReferenceDataDraft,
  ReferenceDataPreviewComparison,
  ReferenceDataVersion,
} from './types'

const ADMIN_DRAFT_KEY = 'cost-monitor-admin-draft-version-v2'
const REFERENCE_DATA_DRAFT_KEY = 'cost-monitor-reference-data-draft-version-v1'

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
  const [presentation, setPresentation] = useState<ConfigurationPresentation | null>(null)
  const [draft, setDraft] = useState<ConfigurationDraft | null>(null)
  const [configuration, setConfiguration] = useState<CostMonitorConfiguration | null>(null)
  const [comparison, setComparison] = useState<ConfigurationComparison | null>(null)
  const [preview, setPreview] = useState<ConfigurationPreviewComparison | null>(null)
  const [referenceActive, setReferenceActive] = useState<ActiveReferenceData | null>(null)
  const [referenceVersions, setReferenceVersions] = useState<ReferenceDataVersion[]>([])
  const [referenceDraft, setReferenceDraft] = useState<ReferenceDataDraft | null>(null)
  const [referenceComparison, setReferenceComparison] = useState<ReferenceDataComparison | null>(null)
  const [referencePreview, setReferencePreview] = useState<ReferenceDataPreviewComparison | null>(null)
  const [calculation, setCalculation] = useState<CalculationRequest>(controlCalculation)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [referenceBusy, setReferenceBusy] = useState<string | null>(null)
  const [referenceError, setReferenceError] = useState<string | null>(null)
  const [referenceNotice, setReferenceNotice] = useState<string | null>(null)

  const refresh = async () => {
    const [nextActive, nextVersions, nextCapabilities, nextPresentation, nextReferenceActive, nextReferenceVersions] = await Promise.all([
      api.activeConfiguration(),
      api.configurationVersions(),
      api.configurationCapabilities(),
      api.configurationPresentation(),
      api.activeReferenceData(),
      api.referenceDataVersions(),
    ])
    setActive(nextActive)
    setVersions(nextVersions)
    setCapabilities(nextCapabilities)
    setPresentation(nextPresentation)
    setReferenceActive(nextReferenceActive)
    setReferenceVersions(nextReferenceVersions)
  }

  useEffect(() => {
    let mounted = true
    async function bootstrap() {
      try {
        await refresh()
        const savedConfigurationVersion = Number(window.localStorage.getItem(ADMIN_DRAFT_KEY))
        if (savedConfigurationVersion) {
          try {
            const savedDraft = await api.configurationDraft(savedConfigurationVersion)
            if (mounted) {
              setDraft(savedDraft)
              setConfiguration(savedDraft.configuration)
            }
          } catch {
            window.localStorage.removeItem(ADMIN_DRAFT_KEY)
          }
        }
        const savedReferenceVersion = Number(window.localStorage.getItem(REFERENCE_DATA_DRAFT_KEY))
        if (savedReferenceVersion) {
          try {
            const savedReferenceDraft = await api.referenceDataDraft(savedReferenceVersion)
            if (mounted) setReferenceDraft(savedReferenceDraft)
          } catch {
            window.localStorage.removeItem(REFERENCE_DATA_DRAFT_KEY)
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

  const createDraft = (base: 'default' | 'active') => run('create', async () => {
    const next = await api.createConfigurationDraft(base)
    setDraft(next)
    setConfiguration(next.configuration)
    setPreview(null)
    setComparison(null)
    window.localStorage.setItem(ADMIN_DRAFT_KEY, String(next.version))
    setNotice(`Создан draft v${next.version} на основе ${base === 'default' ? 'Default' : 'Active'}`)
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

  const deleteDraft = () => run('delete', async () => {
    if (!draft) return
    await api.deleteConfigurationDraft(draft.version)
    window.localStorage.removeItem(ADMIN_DRAFT_KEY)
    setDraft(null)
    setConfiguration(null)
    setPreview(null)
    setComparison(null)
    setNotice(`Draft v${draft.version} удалён`)
  })

  const exportConfiguration = (version: number) => run('export', async () => {
    const { blob, filename } = await api.exportConfiguration(version)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
    URL.revokeObjectURL(url)
    setNotice(`Configuration v${version} выгружена в JSON`)
  })

  const runReference = async (name: string, operation: () => Promise<void>) => {
    setReferenceBusy(name)
    setReferenceError(null)
    setReferenceNotice(null)
    try {
      await operation()
    } catch (caught) {
      setReferenceError(caught instanceof Error ? caught.message : 'Операция Reference Data завершилась ошибкой')
    } finally {
      setReferenceBusy(null)
    }
  }

  const createReferenceDraft = () => runReference('create', async () => {
    const next = await api.createReferenceDataDraft()
    setReferenceDraft(next)
    setReferencePreview(null)
    setReferenceComparison(null)
    window.localStorage.setItem(REFERENCE_DATA_DRAFT_KEY, String(next.version))
    setReferenceNotice(`Создан Reference Data draft v${next.version}`)
  })

  const saveReferenceDraft = async (): Promise<ReferenceDataDraft> => {
    if (!referenceDraft) throw new Error('Сначала создайте Reference Data draft')
    const saved = await api.updateReferenceDataDraft(referenceDraft.version, referenceDraft.reference_data)
    setReferenceDraft(saved)
    return saved
  }

  const saveReference = () => runReference('save', async () => {
    const saved = await saveReferenceDraft()
    setReferenceNotice(`Reference Data draft v${saved.version} сохранён`)
  })

  const validateReference = () => runReference('validate', async () => {
    const saved = await saveReferenceDraft()
    const validated = await api.validateReferenceDataDraft(saved.version)
    setReferenceDraft(validated)
    setReferenceNotice(`Reference Data draft v${validated.version}: VALID`)
  })

  const previewReference = () => runReference('preview', async () => {
    const saved = await saveReferenceDraft()
    setReferencePreview(await api.previewReferenceDataDraft(saved.version, calculation))
    setReferenceNotice('Reference Data preview рассчитан без изменения active version')
  })

  const activateReference = () => runReference('activate', async () => {
    const saved = await saveReferenceDraft()
    await api.validateReferenceDataDraft(saved.version)
    await api.activateReferenceDataDraft(saved.version)
    window.localStorage.removeItem(REFERENCE_DATA_DRAFT_KEY)
    setReferenceDraft(null)
    setReferencePreview(null)
    await refresh()
    setReferenceNotice(`Reference Data v${saved.version} активирована`)
  })

  const rollbackReference = (version: number) => runReference('rollback', async () => {
    await api.rollbackReferenceData(version)
    setReferencePreview(null)
    await refresh()
    setReferenceNotice(`Выполнен rollback Reference Data на v${version}`)
  })

  const compareReference = (left: number, right: number) => runReference('compare', async () => {
    setReferenceComparison(await api.compareReferenceData(left, right))
  })

  return (
    <div className="admin-shell">
      {notice && <div className="toast toast-success" onClick={() => setNotice(null)}>{notice}<button aria-label="Закрыть">×</button></div>}
      {error && <div className="toast toast-error" onClick={() => setError(null)}>{error}<button aria-label="Закрыть">×</button></div>}
      {referenceNotice && <div className="toast toast-success" onClick={() => setReferenceNotice(null)}>{referenceNotice}<button aria-label="Закрыть">×</button></div>}
      {referenceError && <div className="toast toast-error" onClick={() => setReferenceError(null)}>{referenceError}<button aria-label="Закрыть">×</button></div>}
      <AdminPage
        active={active}
        versions={versions}
        capabilities={capabilities}
        presentation={presentation}
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
        onDeleteDraft={deleteDraft}
        onExport={exportConfiguration}
        referenceDataSection={<ReferenceDataAdmin
          active={referenceActive}
          versions={referenceVersions}
          draft={referenceDraft}
          comparison={referenceComparison}
          preview={referencePreview}
          calculation={calculation}
          busy={referenceBusy}
          onReferenceDataChange={(referenceData) => referenceDraft && setReferenceDraft({ ...referenceDraft, reference_data: referenceData })}
          onCreateDraft={createReferenceDraft}
          onSave={saveReference}
          onValidate={validateReference}
          onPreview={previewReference}
          onActivate={activateReference}
          onRollback={rollbackReference}
          onCompare={compareReference}
        />}
      />
    </div>
  )
}
